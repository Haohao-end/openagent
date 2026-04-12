import logging
from dataclasses import dataclass
from typing import Any
from injector import inject
import os
import jwt

from internal.exception import UnauthorizedException

logger = logging.getLogger(__name__)

_INSECURE_PLACEHOLDER_KEYS = frozenset({
    "",
    "your-random-secret-key-here-change-this",
    "change-me",
    "secret",
    "jwt-secret",
    "your-secret-key",
})


@inject
@dataclass
class JwtService:
    """JWT服务"""

    @classmethod
    def _get_secret_key(cls) -> str:
        """获取并校验JWT密钥，拒绝空值和已知的占位符。"""
        secret_key = os.getenv("JWT_SECRET_KEY", "").strip()
        if not secret_key or secret_key.lower() in _INSECURE_PLACEHOLDER_KEYS:
            logger.error(
                "JWT_SECRET_KEY 未设置或使用了不安全的占位符值，请在环境变量中配置一个强随机密钥"
            )
            raise UnauthorizedException("服务端密钥未正确配置，请联系管理员")
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

