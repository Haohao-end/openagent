from dataclasses import dataclass
from injector import inject
from flask import g
from flask_login import current_user
from internal.exception import FailException
from internal.schema.oauth_schema import AuthorizeReq, AuthorizeResp
from internal.service import OAuthService
from pkg.response import success_json, validate_error_json


@inject
@dataclass
class OAuthHandler:
    """第三方授权认证处理器"""
    oauth_service: OAuthService

    def provider(self, provider_name: str):
        """根据传递的提供商名字获取授权认证重定向地址"""
        # 1.根据provider_name获取授权服务提供商
        oauth = self.oauth_service.get_oauth_by_provider_name(provider_name)

        # 2.调用函数获取授权地址
        redirect_url = oauth.get_authorization_url()

        return success_json({"redirect_url": redirect_url})

    def authorize(self, provider_name: str):
        """根据传递的提供商名字+code获取第三方授权信息"""
        # 1.提取请求数据并校验
        req = AuthorizeReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务登录账号/绑定账号
        intent = req.intent.data or "login"
        if intent == "bind":
            if not getattr(current_user, "is_authenticated", False):
                raise FailException("请先登录后再绑定第三方账号")
            credential = self.oauth_service.bind_oauth(
                current_user,
                provider_name,
                req.code.data,
                current_session=getattr(g, "current_account_session", None),
            )
        else:
            credential = self.oauth_service.oauth_login(provider_name, req.code.data)

        return success_json(AuthorizeResp().dump(credential))
