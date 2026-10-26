import base64
import hashlib

from pkg.password.password import (
    PBKDF2_ITERATIONS,
    compare_password,
    hash_password,
)


def _encoded_password(password, salt, iterations):
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return base64.b64encode(digest.hex().encode("ascii"))


def test_hash_password_uses_the_current_iteration_count():
    password = "OpenAgent123"
    salt = b"stable-test-salt"

    hashed = hash_password(password, salt)

    assert PBKDF2_ITERATIONS == 600_000
    assert hashed == hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    ).hex().encode("ascii")


def test_compare_password_accepts_new_and_legacy_hashes():
    password = "OpenAgent123"
    salt = b"stable-test-salt"
    encoded_salt = base64.b64encode(salt)
    current_hash = _encoded_password(password, salt, PBKDF2_ITERATIONS)
    legacy_hash = _encoded_password(password, salt, 10_000)

    assert compare_password(password, current_hash, encoded_salt)
    assert compare_password(password, legacy_hash, encoded_salt)
    assert not compare_password("WrongPassword123", legacy_hash, encoded_salt)
