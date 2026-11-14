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

            # 5.接信息得到API密钥记录
            api_key_record = self.api_key_service.get_api_by_by_credential(api_key)

            # 6.判断API密钥记录是否存在/是否被激活 如果不存在则抛出错误
            expires_at = getattr(api_key_record, "expires_at", None) if api_key_record else None
            if (
                not api_key_record
                or not api_key_record.is_active
                or (
                    expires_at is not None
                    and ensure_utc_naive(expires_at) <= utc_now_naive()
                )
            ):
                raise UnauthorizedException("该密钥不存在或未激活")

            scopes = getattr(api_key_record, "scopes", None)
            if scopes is not None and not self._api_key_has_scope(scopes, request.endpoint):
                raise ForbiddenException("该密钥没有调用此接口的权限")

            try:
                self.api_key_service.record_api_key_request(api_key_record)
            except SQLAlchemyError as error:
                # Usage metadata is best-effort; tracking failures must not reject valid credentials.
                logger.warning(
                    "api_key_usage_update_failed error_class=%s",
                    type(error).__name__,
                )

            # 7.获取密钥账号信息并返回
            return api_key_record.account
        else:
            return None

    @classmethod
    def _validate_credential(cls, request: Request) -> str:
        """校验请求头中的凭证信息 涵盖access_token和api_key"""
        # 1.提取请求投headers中的信息
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise UnauthorizedException("该接口需要授权才能访问 请登陆后重试")

        # 3.请求信息中没有空格分隔符,则校验失败 格式为Authorization:Bearer credential
        if " " not in auth_header:
            raise UnauthorizedException("该接口需要授权才能访问 验证格式失败")

        # 4.分割授权信息 必须符合Bearer access_token格式
        auth_schema, credential = auth_header.split(None, 1)
        if auth_schema.lower() != "bearer":
            raise UnauthorizedException("该接口需要授权才能访问 验证格式失败")

        return credential

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


