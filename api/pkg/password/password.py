import base64
import binascii
import hashlib
import re
from typing import Any

# 密码校验正则，密码最少包含一个字母、一个数字，并且长度在8-16
password_pattern = r"^(?=.*[a-zA-Z])(?=.*\d).{8,16}$"


def validate_password(password: str, pattern: str = password_pattern):
    """校验传入的密码是否符合相应的匹配规则"""
    if re.match(pattern, password) is None:
        raise ValueError("密码规则校验失败，至少包含一个字母，一个数字，并且长度为8-16位")
    return


PBKDF2_ITERATIONS = 600000


def hash_password(password: str, salt: Any, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    """将传入的密码+颜值进行哈希加密"""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return binascii.hexlify(dk)


_LEGACY_PBKDF2_ITERATIONS = 10000


def compare_password(password: str, password_hashed_base64: Any, salt_base64: Any) -> bool:
    """根据传递的密码+颜值校验比对是否一致，同时兼容旧迭代次数的密码哈希"""
    salt = base64.b64decode(salt_base64)
    expected = base64.b64decode(password_hashed_base64)
    if hash_password(password, salt) == expected:
        return True
    return hash_password(password, salt, iterations=_LEGACY_PBKDF2_ITERATIONS) == expected
