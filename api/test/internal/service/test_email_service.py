from datetime import timedelta
from types import SimpleNamespace

from flask import Flask
import pytest

from internal.exception import FailException
from internal.service.email_service import EmailService


class TestEmailService:
    def test_resolve_client_ip_should_use_forwarded_for_first_ip(self):
        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={"X-Forwarded-For": "1.1.1.1, 2.2.2.2"},
            environ_base={"REMOTE_ADDR": "9.9.9.9"},
        ):
            assert EmailService._resolve_client_ip() == "1.1.1.1"

    def test_resolve_client_ip_should_fallback_to_remote_addr_or_unknown(self):
        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "8.8.8.8"}):
            assert EmailService._resolve_client_ip() == "8.8.8.8"

        with app.test_request_context("/"):
            assert EmailService._resolve_client_ip() == "unknown"

    def test_generate_verification_code_should_match_length_and_digits_only(self):
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        code = service.generate_verification_code(length=8)

        assert len(code) == 8
        assert code.isdigit() is True

    def test_send_verification_code_should_store_code_and_send_mail(self, monkeypatch):
        setex_calls = []
        delete_calls = []
        expire_calls = []
        incr_calls = []
        sent_messages = []
        service = EmailService(mail=SimpleNamespace(send=lambda msg: sent_messages.append(msg)))

        class _FakeMessage:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        redis_stub = SimpleNamespace(
            exists=lambda _key: False,
            ttl=lambda _key: -2,
            incr=lambda key: incr_calls.append(key) or 1,
            expire=lambda key, ttl: expire_calls.append((key, ttl)),
            setex=lambda key, ttl, value: setex_calls.append((key, ttl, value)),
            delete=lambda key: delete_calls.append(key),
        )

        monkeypatch.setattr("internal.service.email_service.Message", _FakeMessage)
        monkeypatch.setattr(service, "generate_verification_code", lambda length=6: "123456")
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)

        code = service.send_verification_code("demo@example.com")

        assert code == "123456"
        assert incr_calls == [
            "password_reset:send_count:demo@example.com",
            "password_reset:send_count_ip:unknown",
        ]
        assert expire_calls == [
            ("password_reset:send_count:demo@example.com", 3600),
            ("password_reset:send_count_ip:unknown", 3600),
        ]
        assert len(setex_calls) == 3
        assert setex_calls[0][0] == "password_reset:demo@example.com"
        assert setex_calls[0][1] == timedelta(seconds=300)
        assert setex_calls[0][2] == "123456"
        assert setex_calls[1][0] == "password_reset:send_cooldown:demo@example.com"
        assert setex_calls[1][1] == timedelta(seconds=60)
        assert setex_calls[1][2] == "1"
        assert setex_calls[2][0] == "password_reset:send_cooldown_ip:unknown"
        assert setex_calls[2][1] == timedelta(seconds=60)
        assert setex_calls[2][2] == "1"
        assert delete_calls == [
            "password_reset:verify_attempt:demo@example.com",
            "password_reset:verify_lock:demo@example.com",
        ]
        assert len(sent_messages) == 1
        assert sent_messages[0].recipients == ["demo@example.com"]
        assert "123456" in sent_messages[0].body

    def test_send_verification_code_should_raise_when_mail_send_failed(self, monkeypatch):
        setex_calls = []
        delete_calls = []

        def _raise_send_error(_msg):
            raise RuntimeError("smtp down")

        service = EmailService(mail=SimpleNamespace(send=_raise_send_error))

        class _FakeMessage:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        redis_stub = SimpleNamespace(
            exists=lambda _key: False,
            ttl=lambda _key: -2,
            incr=lambda _key: 1,
            expire=lambda *_args: None,
            setex=lambda key, ttl, value: setex_calls.append((key, ttl, value)),
            delete=lambda key: delete_calls.append(key),
        )

        monkeypatch.setattr("internal.service.email_service.Message", _FakeMessage)
        monkeypatch.setattr(service, "generate_verification_code", lambda length=6: "654321")
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)

        app = Flask(__name__)
        with app.app_context():
            with pytest.raises(FailException, match="邮件发送失败"):
                service.send_verification_code("demo@example.com")

        assert len(setex_calls) == 3
        assert "password_reset:demo@example.com" in delete_calls
        assert "password_reset:send_cooldown:demo@example.com" in delete_calls
        assert "password_reset:send_cooldown_ip:unknown" in delete_calls

    def test_send_verification_code_should_raise_when_in_cooldown(self, monkeypatch):
        redis_stub = SimpleNamespace(
            exists=lambda key: key == "password_reset:send_cooldown:demo@example.com",
            ttl=lambda _key: 30,
            incr=lambda _key: (_ for _ in ()).throw(AssertionError("incr should not be called")),
            expire=lambda *_args: None,
            setex=lambda *_args: None,
            delete=lambda *_args: None,
        )
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        with pytest.raises(FailException, match="30秒后再试"):
            service.send_verification_code("demo@example.com")

    @pytest.mark.parametrize("ttl_value", [0, -1, -2, -999999])
    def test_send_verification_code_should_use_default_cooldown_when_ttl_non_positive(self, monkeypatch, ttl_value):
        redis_stub = SimpleNamespace(
            exists=lambda key: key == "password_reset:send_cooldown:demo@example.com",
            ttl=lambda _key: ttl_value,
            incr=lambda _key: (_ for _ in ()).throw(AssertionError("incr should not be called")),
            expire=lambda *_args: None,
            setex=lambda *_args: None,
            delete=lambda *_args: None,
        )
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        with pytest.raises(FailException, match=f"{EmailService.SEND_COOLDOWN_SECONDS}秒后再试"):
            service.send_verification_code("demo@example.com")

    def test_send_verification_code_should_raise_when_send_count_exceeded(self, monkeypatch):
        expire_calls = []
        redis_stub = SimpleNamespace(
            exists=lambda _key: False,
            ttl=lambda _key: -2,
            incr=lambda _key: EmailService.MAX_SEND_COUNT_PER_WINDOW + 1,
            expire=lambda key, ttl: expire_calls.append((key, ttl)),
            setex=lambda *_args: (_ for _ in ()).throw(AssertionError("setex should not be called")),
            delete=lambda *_args: None,
        )
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        with pytest.raises(FailException, match="次数过多"):
            service.send_verification_code("demo@example.com")

        assert expire_calls == []

    def test_send_verification_code_should_raise_when_ip_in_cooldown(self, monkeypatch):
        redis_stub = SimpleNamespace(
            exists=lambda key: key == "password_reset:send_cooldown_ip:unknown",
            ttl=lambda _key: 25,
            incr=lambda _key: (_ for _ in ()).throw(AssertionError("incr should not be called")),
            expire=lambda *_args: None,
            setex=lambda *_args: None,
            delete=lambda *_args: None,
        )
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        with pytest.raises(FailException, match="25秒后再试"):
            service.send_verification_code("demo@example.com")

    def test_send_verification_code_should_raise_when_ip_send_count_exceeded(self, monkeypatch):
        expire_calls = []

        def _incr(key):
            if key == "password_reset:send_count:demo@example.com":
                return 1
            if key == "password_reset:send_count_ip:unknown":
                return EmailService.MAX_SEND_COUNT_PER_IP_PER_WINDOW + 1
            raise AssertionError(f"unexpected key: {key}")

        redis_stub = SimpleNamespace(
            exists=lambda _key: False,
            ttl=lambda _key: -2,
            incr=_incr,
            expire=lambda key, ttl: expire_calls.append((key, ttl)),
            setex=lambda *_args: (_ for _ in ()).throw(AssertionError("setex should not be called")),
            delete=lambda *_args: None,
        )
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        with pytest.raises(FailException, match="次数过多"):
            service.send_verification_code("demo@example.com")

        assert expire_calls == [("password_reset:send_count:demo@example.com", 3600)]

    def test_verify_code_should_delete_keys_when_code_matches(self, monkeypatch):
        delete_calls = []
        redis_stub = SimpleNamespace(
            exists=lambda _key: False,
            get=lambda _key: b"112233",
            incr=lambda _key: 1,
            ttl=lambda _key: 120,
            expire=lambda *_args: None,
            setex=lambda *_args: None,
            delete=lambda key: delete_calls.append(key),
        )
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        is_valid = service.verify_code("demo@example.com", "112233")

        assert is_valid is True
        assert delete_calls == [
            "password_reset:demo@example.com",
            "password_reset:verify_attempt:demo@example.com",
            "password_reset:verify_lock:demo@example.com",
        ]

    def test_verify_code_should_raise_when_account_is_locked(self, monkeypatch):
        redis_stub = SimpleNamespace(
            exists=lambda key: key == "password_reset:verify_lock:demo@example.com",
            get=lambda _key: (_ for _ in ()).throw(AssertionError("should not read code when locked")),
            incr=lambda _key: (_ for _ in ()).throw(AssertionError("incr should not be called")),
            ttl=lambda _key: 120,
            expire=lambda *_args: None,
            setex=lambda *_args: None,
            delete=lambda *_args: None,
        )
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        with pytest.raises(FailException, match="错误次数过多"):
            service.verify_code("demo@example.com", "123456")

    def test_verify_code_should_return_false_when_code_missing(self, monkeypatch):
        redis_stub = SimpleNamespace(
            exists=lambda _key: False,
            get=lambda _key: None,
            incr=lambda _key: (_ for _ in ()).throw(AssertionError("incr should not be called")),
            ttl=lambda _key: 120,
            expire=lambda *_args: None,
            setex=lambda *_args: None,
            delete=lambda *_args: None,
        )
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        assert service.verify_code("demo@example.com", "123456") is False

    def test_verify_code_should_raise_when_attempts_exceeded(self, monkeypatch):
        setex_calls = []
        delete_calls = []
        redis_stub = SimpleNamespace(
            exists=lambda key: False,
            get=lambda _key: b"123456",
            incr=lambda _key: 5,
            ttl=lambda _key: 180,
            expire=lambda *_args: None,
            setex=lambda key, ttl, value: setex_calls.append((key, ttl, value)),
            delete=lambda key: delete_calls.append(key),
        )
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        with pytest.raises(FailException, match="错误次数过多"):
            service.verify_code("demo@example.com", "bad-code")

        assert setex_calls == [
            (
                "password_reset:verify_lock:demo@example.com",
                timedelta(seconds=900),
                "1",
            )
        ]
        assert delete_calls == [
            "password_reset:demo@example.com",
            "password_reset:verify_attempt:demo@example.com",
        ]

    def test_verify_code_should_set_attempt_ttl_and_return_false_on_first_wrong_code(self, monkeypatch):
        expire_calls = []
        redis_stub = SimpleNamespace(
            exists=lambda _key: False,
            get=lambda _key: b"654321",
            incr=lambda _key: 1,
            ttl=lambda _key: 180,
            expire=lambda key, ttl: expire_calls.append((key, ttl)),
            setex=lambda *_args: None,
            delete=lambda *_args: None,
        )
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        result = service.verify_code("demo@example.com", "bad-code")

        assert result is False
        assert expire_calls == [("password_reset:verify_attempt:demo@example.com", 180)]

    @pytest.mark.parametrize(
        "code_ttl,expected_attempt_ttl",
        [
            (0, EmailService.CODE_TTL_SECONDS),
            (-1, EmailService.CODE_TTL_SECONDS),
            (-2, EmailService.CODE_TTL_SECONDS),
            (10**6, 10**6),
        ],
    )
    def test_verify_code_should_handle_attempt_ttl_boundary_values(self, monkeypatch, code_ttl, expected_attempt_ttl):
        expire_calls = []
        redis_stub = SimpleNamespace(
            exists=lambda _key: False,
            get=lambda _key: b"654321",
            incr=lambda _key: 1,
            ttl=lambda _key: code_ttl,
            expire=lambda key, ttl: expire_calls.append((key, ttl)),
            setex=lambda *_args: None,
            delete=lambda *_args: None,
        )
        monkeypatch.setattr("internal.service.email_service.redis_client", redis_stub)
        service = EmailService(mail=SimpleNamespace(send=lambda _msg: None))

        result = service.verify_code("demo@example.com", "bad-code")

        assert result is False
        assert expire_calls == [
            ("password_reset:verify_attempt:demo@example.com", expected_attempt_ttl)
        ]
