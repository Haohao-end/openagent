from typing import Optional
from dataclasses import dataclass
from flask import Request
from injector import inject
from internal.model import Account
from internal.exception import UnauthorizedException
from internal.service import JwtService, AccountService, ApiKeyService

@inject
@dataclass
class Middleware:
    """应用中间件 可用重写 request_loader 和 unauthorized_handler"""
    jwt_service: JwtService
    api_key_service: ApiKeyService
    account_service: AccountService

    def request_loader(self, request: Request) -> Optional[Account]:
        """登陆管理器的请求加载器"""
        # 1.单独位llmops路由蓝图创建请求加载器
        if request.blueprint == "llmops":
            # 2.校验获取access_token
            access_token = self._validate_credential(request)

            # 3.解析token信息得到用户信息并返回
            payload = self.jwt_service.parse_token(access_token)
            account_id = payload.get("sub")
            return self.account_service.get_account(account_id)
        elif request.blueprint == "openapi":
            # 4.校验获取api_key
            api_key = self._validate_credential(request)

            # 5.接信息得到API密钥记录
            api_key_record = self.api_key_service.get_api_by_by_credential(api_key)

            # 6.判断API密钥记录是否存在/是否被激活 如果不存在则抛出错误
            if not api_key_record or not api_key_record.is_active:
                raise UnauthorizedException("该密钥不存在或未激活")

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


