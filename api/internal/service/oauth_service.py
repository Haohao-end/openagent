import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from flask import request, has_request_context, current_app
from injector import inject
from internal.exception import NotFoundException
from internal.model import AccountOAuth
from pkg.oauth import OAuth, GithubOAuth, GoogleOAuth
from pkg.sqlalchemy import SQLAlchemy
from .account_service import AccountService
from .base_service import BaseService
from .jwt_service import JwtService


@inject
@dataclass
class OAuthService(BaseService):
    """第三方授权你认证服务"""
    db: SQLAlchemy
    jwt_service: JwtService
    account_service: AccountService

    @classmethod
    def _allowed_origins(cls) -> set[str]:
        if has_request_context():
            configured = current_app.config.get("OAUTH_ALLOWED_ORIGINS")
            if isinstance(configured, (list, tuple, set)):
                return {str(item).strip().rstrip("/") for item in configured if str(item).strip()}
            if isinstance(configured, str) and configured.strip():
                return {item.strip().rstrip("/") for item in configured.split(",") if item.strip()}

        raw = (os.getenv("OAUTH_ALLOWED_ORIGINS") or "").strip()
        if not raw:
            return set()
        return {item.strip().rstrip("/") for item in raw.split(",") if item.strip()}

    @classmethod
    def _resolve_redirect_uri(cls, provider_name: str, env_key: str) -> str:
        """优先使用固定回调地址，仅当 Origin 在白名单中时允许动态拼接。"""
        configured_redirect_uri = (os.getenv(env_key) or "").strip()

        if not has_request_context():
            return configured_redirect_uri

        origin = (request.headers.get("Origin") or "").strip().rstrip("/")
        if not origin:
            return configured_redirect_uri

        allowed_origins = cls._allowed_origins()
        if origin in allowed_origins:
            return f"{origin}/auth/authorize/{provider_name}"

        return configured_redirect_uri

    @classmethod
    def get_all_oauth(cls) -> dict[str, OAuth]:
        """获取LLMOps集成的所有第三方授权认证方式"""
        # 1.实例化集成的第三方授权认证OAuth
        github = GithubOAuth(
            client_id=os.getenv("GITHUB_CLIENT_ID"),
            client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
            redirect_uri=cls._resolve_redirect_uri("github", "GITHUB_REDIRECT_URI"),
        )
        google = GoogleOAuth(
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            redirect_uri=cls._resolve_redirect_uri("google", "GOOGLE_REDIRECT_URI"),
        )

        # 2.构建字典并返回
        return {
            "github": github,
            "google": google,
        }

    @classmethod
    def get_oauth_by_provider_name(cls, provider_name: str) -> OAuth:
        """根据传递的服务提供商名字获取授权服务"""
        all_oauth = cls.get_all_oauth()
        oauth = all_oauth.get(provider_name)

        if oauth is None:
            raise NotFoundException(f"该授权方式[{provider_name}]不存在")

        return oauth

    def oauth_login(self, provider_name: str, code: str) -> dict[str, Any]:
        """第三方OAuth授权认证登录，返回授权凭证以及过期时间"""
        # 1.根据传递的provider_name获取oauth
        oauth = self.get_oauth_by_provider_name(provider_name)

        # 2.根据code从第三方登录服务中获取access_token
        oauth_access_token = oauth.get_access_token(code)

        # 3.根据获取到的token提取user_info信息
        oauth_user_info = oauth.get_user_info(oauth_access_token)

        # 4.根据provider_name+openid获取授权记录
        account_oauth = self.account_service.get_account_oauth_by_provider_name_and_openid(
            provider_name,
            oauth_user_info.id,
        )
        if not account_oauth:
            # 5.该授权认证方式是第一次登录，查询邮箱是否存在
            account = self.account_service.get_account_by_email(oauth_user_info.email)
            if not account:
                # 6.账号不存在，注册账号
                account = self.account_service.create_account(
                    name=oauth_user_info.name,
                    email=oauth_user_info.email,
                )
            # 7.添加授权认证记录
            account_oauth = self.create(
                AccountOAuth,
                account_id=account.id,
                provider=provider_name,
                openid=oauth_user_info.id,
                encrypted_token=oauth_access_token,
            )
        else:
            # 8.查找账号信息
            account = self.account_service.get_account(account_oauth.account_id)

        # 9.更新账号信息，涵盖最后一次登录时间，以及ip地址
        self.update(
            account,
            last_login_at=datetime.now(UTC),
            last_login_ip=request.remote_addr,
        )
        self.update(
            account_oauth,
            encrypted_token=oauth_access_token,
        )

        # 10.生成授权凭证信息
        expire_at = int((datetime.now() + timedelta(days=30)).timestamp())
        payload = {
            "sub": str(account.id),
            "iss": "llmops",
            "exp": expire_at,
        }
        access_token = self.jwt_service.generate_token(payload)

        return {
            "expire_at": expire_at,
            "access_token": access_token,
        }
