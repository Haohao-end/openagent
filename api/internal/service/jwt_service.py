from dataclasses import dataclass
from typing import Any
from injector import inject
import os
import jwt

from internal.exception import UnauthorizedException

_JWT_SECRET_PLACEHOLDERS = {"your-random-secret-key-here-change-this"}


@inject
@dataclass
class JwtService:
    """JWT服务"""

    @classmethod
    def _get_secret_key(cls) -> str:
        secret_key = (os.getenv("JWT_SECRET_KEY") or "").strip()
        if not secret_key or secret_key in _JWT_SECRET_PLACEHOLDERS:
            raise UnauthorizedException("JWT secret key is not configured")
        return secret_key

    @classmethod
    def generate_token(cls, payload: dict[str, Any]) -> str:
        """根据传递的载荷信息生成token信息"""
        secret_key = cls._get_secret_key()
        return jwt.encode(payload, secret_key, algorithm='HS256')

    @classmethod
    def parse_token(cls, token: str) -> dict[str, Any]:
        """解析传入的token信息得到载荷"""
        secret_key = cls._get_secret_key()
        try:
            return jwt.decode(token, secret_key, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException('授权认证凭证已过期,请重新登陆')
        except jwt.InvalidTokenError:
            raise UnauthorizedException('解析token出错 请重新登录')
        except Exception:
            raise UnauthorizedException("授权认证失败,请重新登录")

