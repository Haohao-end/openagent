import base64
import binascii
import hashlib
import hmac
import re
from typing import Any

# 密码校验正则，密码最少包含一个字母、一个数字，并且长度在8-16
password_pattern = r"^(?=.*[a-zA-Z])(?=.*\d).{8,16}$"


def validate_password(password: str, pattern: str = password_pattern):
    """校验传入的密码是否符合相应的匹配规则"""
    if re.match(pattern, password) is None:
        raise ValueError("密码规则校验失败，至少包含一个字母，一个数字，并且长度为8-16位")
    return


PBKDF2_ITERATIONS = 600_000
_LEGACY_PBKDF2_ITERATIONS = 10_000


def hash_password(password: str, salt: Any, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    """将传入的密码和盐值进行哈希加密。"""
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return binascii.hexlify(digest)


def compare_password(password: str, password_hashed_base64: Any, salt_base64: Any) -> bool:
    """校验密码，兼容升级前使用 10,000 轮 PBKDF2 的已有哈希。"""
    salt = base64.b64decode(salt_base64)
    expected = base64.b64decode(password_hashed_base64)
    for iterations in (PBKDF2_ITERATIONS, _LEGACY_PBKDF2_ITERATIONS):
        candidate = hash_password(password, salt, iterations=iterations)
        if hmac.compare_digest(candidate, expected):
            return True
    return False
