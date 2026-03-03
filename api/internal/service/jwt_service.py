from dataclasses import dataclass
from typing import Any
from injector import inject
import os
import jwt

from internal.exception import UnauthorizedException


@inject
@dataclass
class JwtService:
    """JWT服务"""

    @classmethod
    def generate_token(cls, payload: dict[str, Any]) -> str:
        """根据传递的载荷信息生成token信息"""
        secret_key = os.getenv('JWT_SECRET_KEY')
        return jwt.encode(payload, secret_key, algorithm='HS256')

    @classmethod
    def parse_token(cls, token: str) -> dict[str, Any]:
        """解析传入的token信息得到载荷"""
        secret_key = os.getenv('JWT_SECRET_KEY')
        try:
            return jwt.decode(token, secret_key, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException('授权认证凭证已过期,请重新登陆')
        except jwt.InvalidTokenError:
            raise UnauthorizedException('解析token出错 请重新登录')
        except Exception:
            raise UnauthorizedException("授权认证失败,请重新登录")

