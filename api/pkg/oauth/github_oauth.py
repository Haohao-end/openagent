import urllib.parse
import requests
from .oauth import OAuth, OAuthUserInfo
import dotenv
import certifi
import os
# 加载环境变量
dotenv.load_dotenv()
# 修复SSL证书路径
os.environ["SSL_CERT_FILE"] = certifi.where()



class GithubOAuth(OAuth):
    """GithubOAuth第三方授权认证类"""
    _AUTHORIZE_URL = "https://github.com/login/oauth/authorize"  # 跳转授权接口
    _ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"  # 获取授权令牌接口
    _USER_INFO_URL = "https://api.github.com/user"  # 获取用户信息接口
    _EMAIL_INFO_URL = "https://api.github.com/user/emails"  # 获取用户邮箱接口

    def get_provider(self) -> str:
        return "github"

    def get_authorization_url(self) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:email",  # 只请求用户的基本信息
        }
        return f"{self._AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def get_access_token(self, code: str) -> str:
        # 1.组装请求数据
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        headers = {"Accept": "application/json"}

        # 2.发起post请求并获取相应的数据
        resp = requests.post(self._ACCESS_TOKEN_URL, data=data, headers=headers)
        resp.raise_for_status()
        resp_json = resp.json()

        # 3.提取access_token对应的数据
        access_token = resp_json.get("access_token")
        if not access_token:
            raise ValueError(f"Github OAuth授权失败: {resp_json}")

        return access_token

    def get_raw_user_info(self, token: str) -> dict:
        # 1.组装请求数据
        headers = {"Authorization": f"token {token}"}

        # 2.发起get请求获取用户数据
        resp = requests.get(self._USER_INFO_URL, headers=headers)
        resp.raise_for_status()
        raw_info = resp.json()

        # 3.发起get请求获取用户邮箱
        email_resp = requests.get(self._EMAIL_INFO_URL, headers=headers)
        email_resp.raise_for_status()
        email_info = email_resp.json()

        # 4.提取邮箱数据
        primary_email = next((email for email in email_info if email.get("primary", None)), None)

        return {**raw_info, "email": primary_email.get("email", None)}

    def _transform_user_info(self, raw_info: dict) -> OAuthUserInfo:
        email = raw_info.get("email")
        if not email:
            email = f"{raw_info.get('id')}+{raw_info.get('login')}@user.no-reply@github.com"

        name = raw_info.get("name")
        if not name:  # 如果 name 不存在，使用 login（GitHub 用户名）
            name = raw_info.get("login", "GitHub User")  # 如果 login 也没有，用默认值

        return OAuthUserInfo(
            id=str(raw_info.get("id")),
            name=str(name),  # 确保 name 不会是 None
            email=str(email),
        )
