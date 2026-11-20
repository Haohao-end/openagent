import logging
from typing import Optional
from dataclasses import dataclass
from flask import Request, g
from injector import inject
from sqlalchemy.exc import SQLAlchemyError
from internal.model import Account
from internal.exception import ForbiddenException, UnauthorizedException
from internal.lib.helper import ensure_utc_naive, utc_now_naive
from internal.model.api_key import API_KEY_SCOPE_OPENAPI_CHAT, API_KEY_SUPPORTED_SCOPES
from internal.service import JwtService, AccountService, ApiKeyService

_API_KEY_SCOPE_BY_ENDPOINT = {
    "openapi.chat": API_KEY_SCOPE_OPENAPI_CHAT,
}
logger = logging.getLogger(__name__)


@inject
@dataclass
class Middleware:
    """应用中间件 可用重写 request_loader 和 unauthorized_handler"""
    jwt_service: JwtService
    api_key_service: ApiKeyService
    account_service: AccountService

    def request_loader(self, request: Request) -> Optional[Account]:
        """登陆管理器的请求加载器"""
        g.current_account_session = None
        g.current_access_token_payload = None

        # 1.单独位llmops路由蓝图创建请求加载器
        if request.blueprint == "llmops":
            # 2.校验获取access_token
            access_token = self._validate_credential(request)

            # 3.解析token信息得到用户信息并返回
            payload = self.jwt_service.parse_token(access_token)
            g.current_access_token_payload = payload
            g.current_account_session = self.account_service.validate_access_session(payload)
            account_id = payload.get("sub")
            return self.account_service.get_account(account_id)
        elif request.blueprint == "openapi":
            # 4.校验获取api_key
            api_key = self._validate_credential(request)

            # 5.根据凭证获取API密钥记录并严格按序校验
            api_key_record = self.api_key_service.get_api_by_by_credential(api_key)
            if not api_key_record or not getattr(api_key_record, "is_active", False):
                raise UnauthorizedException("该密钥不存在或未激活")

            expires_at = getattr(api_key_record, "expires_at", None)
            if expires_at is not None and ensure_utc_naive(expires_at) <= utc_now_naive():
                raise UnauthorizedException("该密钥不存在或未激活")

            endpoint = getattr(request, "endpoint", None)
            if endpoint:
                scopes = getattr(api_key_record, "scopes", None)
                effective_scopes = [API_KEY_SCOPE_OPENAPI_CHAT] if scopes is None else scopes
                if not self._api_key_has_scope(effective_scopes, endpoint):
                    raise ForbiddenException("该密钥没有调用此接口的权限")

            # 6.所有凭证与权限校验通过后，再加载绑定账号
            account = getattr(api_key_record, "account", None)
            if not account:
                raise UnauthorizedException("该密钥不存在或未激活")

            # 7.校验接口调用配额与速率限制
            if hasattr(self.api_key_service, "check_rate_limit"):
                allowed, _, _ = self.api_key_service.check_rate_limit(api_key_record)
                if not allowed:
                    raise ForbiddenException("API密钥调用频率超出限制，请稍后重试")

            try:
                self.api_key_service.record_api_key_request(api_key_record)
            except Exception as error:
                # Usage metadata is best-effort; tracking failures must not reject valid credentials.
                logger.warning(
                    "api_key_usage_update_failed error_class=%s",
                    type(error).__name__,
                )

            # 7.获取密钥账号信息并返回
            return account
        else:
            return None

    @classmethod
    def _validate_credential(cls, request: Request) -> str:
        """校验请求头中的凭证信息 涵盖access_token和api_key"""
        # 1.提取请求投headers中的信息
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise UnauthorizedException("该接口需要授权才能访问 请登陆后重试")

        # 2.分割授权信息 必须符合Bearer credential格式
        parts = auth_header.strip().split(None, 1)
        if len(parts) != 2:
            raise UnauthorizedException("该接口需要授权才能访问 验证格式失败")

        auth_schema, credential = parts
        if auth_schema.lower() != "bearer" or not credential.strip():
            raise UnauthorizedException("该接口需要授权才能访问 验证格式失败")

        return credential.strip()

    @staticmethod
    def _api_key_has_scope(scopes: object, endpoint: Optional[str]) -> bool:
        if (
            not isinstance(scopes, list)
            or any(not isinstance(scope, str) for scope in scopes)
            or not set(scopes).issubset(API_KEY_SUPPORTED_SCOPES)
        ):
            return False
        required_scope = _API_KEY_SCOPE_BY_ENDPOINT.get(endpoint or "")
        return required_scope is not None and required_scope in scopes


