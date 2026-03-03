from datetime import datetime, timedelta, timezone

import pytest

from internal.exception import UnauthorizedException
from internal.service.jwt_service import JwtService


class TestJwtService:
    def test_generate_and_parse_token(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-with-32-bytes-min-123456")

        token = JwtService.generate_token({"sub": "u-1"})
        payload = JwtService.parse_token(token)

        assert payload["sub"] == "u-1"

    def test_parse_invalid_token_should_raise(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-with-32-bytes-min-123456")

        with pytest.raises(UnauthorizedException) as exc_info:
            JwtService.parse_token("invalid.token.value")

        assert "解析token出错" in str(exc_info.value)

    def test_parse_expired_token_should_raise(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-with-32-bytes-min-123456")
        expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)

        token = JwtService.generate_token({"sub": "u-1", "exp": expired_at})

        with pytest.raises(UnauthorizedException) as exc_info:
            JwtService.parse_token(token)

        assert "已过期" in str(exc_info.value)

    def test_parse_token_should_hide_unexpected_exception_message(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-with-32-bytes-min-123456")
        monkeypatch.setattr(
            "internal.service.jwt_service.jwt.decode",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("decode boom")),
        )

        with pytest.raises(UnauthorizedException) as exc_info:
            JwtService.parse_token("token")

        assert "授权认证失败" in str(exc_info.value)
