import os
import urllib.parse

import certifi
import dotenv
import requests

from .oauth import OAuth, OAuthUserInfo

# 加载环境变量
dotenv.load_dotenv()

# 修复SSL证书路径
os.environ["SSL_CERT_FILE"] = certifi.where()


class GoogleOAuth(OAuth):
    """Google OAuth第三方授权认证类"""

    _AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    _ACCESS_TOKEN_URL = "https://oauth2.googleapis.com/token"
    _USER_INFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

    def get_provider(self) -> str:
        return "google"

    def get_authorization_url(self) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "response_mode": "query",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "select_account",
        }
        return f"{self._AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def get_access_token(self, code: str) -> str:
        # 1.组装请求数据
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        # 2.发起post请求并获取响应数据
        resp = requests.post(self._ACCESS_TOKEN_URL, data=data, timeout=15)
        resp.raise_for_status()
        resp_json = resp.json()

        # 3.提取access_token对应的数据
        access_token = resp_json.get("access_token")
        if not access_token:
            raise ValueError(f"Google OAuth授权失败: {resp_json}")

        return access_token

    def get_raw_user_info(self, token: str) -> dict:
        # 1.组装请求数据
        headers = {"Authorization": f"Bearer {token}"}

        # 2.发起get请求获取用户数据
        resp = requests.get(self._USER_INFO_URL, headers=headers, timeout=15)
        resp.raise_for_status()

        return resp.json()

    def _transform_user_info(self, raw_info: dict) -> OAuthUserInfo:
        user_id = str(raw_info.get("sub", ""))
        name = str(raw_info.get("name") or raw_info.get("given_name") or "Google User")
        email = raw_info.get("email")
        if not email:
            email = f"{user_id}@user.no-reply.google.com"

        return OAuthUserInfo(
            id=user_id,
            name=name,
            email=str(email),
        )
