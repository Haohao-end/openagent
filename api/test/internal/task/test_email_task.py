from types import SimpleNamespace
import socket
from datetime import timedelta


def test_send_verification_email_task_should_build_message_and_send(monkeypatch):
    sent_messages = []
    setex_calls = []
    delete_calls = []
    fake_mail = SimpleNamespace(send=lambda msg: sent_messages.append(msg))
    injector = SimpleNamespace(get=lambda _cls: fake_mail)

    monkeypatch.setattr("app.http.app.injector", injector)
    monkeypatch.setattr(
        "internal.task.email_task.Message",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        "internal.task.email_task.redis_client",
        SimpleNamespace(
            setex=lambda key, ttl, value: setex_calls.append((key, ttl, value)),
            delete=lambda key: delete_calls.append(key),
        ),
    )
    monkeypatch.setattr(
        "internal.service.email_service.EmailService.generate_verification_code",
        staticmethod(lambda length=6: "123456"),
    )

    from internal.task.email_task import send_verification_email_task

    send_verification_email_task.run(
        email="demo@example.com",
        scene="password_reset",
        client_ip="unknown",
    )

    assert len(sent_messages) == 1
    assert sent_messages[0].subject == "【OpenAgent】密码重置验证码"
    assert sent_messages[0].recipients == ["demo@example.com"]
    assert "123456" in sent_messages[0].body
    assert "123456" in sent_messages[0].html
    assert setex_calls == [
        ("password_reset:demo@example.com", timedelta(seconds=300), "123456"),
        ("password_reset:send_cooldown:demo@example.com", timedelta(seconds=60), "1"),
        ("password_reset:send_cooldown_ip:unknown", timedelta(seconds=60), "1"),
    ]
    assert delete_calls == [
        "password_reset:verify_attempt:demo@example.com",
        "password_reset:verify_lock:demo@example.com",
        "password_reset:send_pending:demo@example.com",
        "password_reset:send_pending_ip:unknown",
    ]


def test_send_verification_email_task_should_prefer_ipv4_server_and_restore(monkeypatch):
    send_servers = []
    timeout_values = []
    setex_calls = []
    delete_calls = []

    def _fake_send(_msg):
        send_servers.append(fake_mail.server)
        timeout_values.append(socket.getdefaulttimeout())

    fake_mail = SimpleNamespace(server="smtp.qq.com", send=_fake_send)
    injector = SimpleNamespace(get=lambda _cls: fake_mail)

    monkeypatch.setattr("app.http.app.injector", injector)
    monkeypatch.setattr(
        "internal.task.email_task.Message",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        "internal.task.email_task.current_app",
        SimpleNamespace(config={"MAIL_TIMEOUT": 10}),
    )
    monkeypatch.setattr(
        "internal.task.email_task.redis_client",
        SimpleNamespace(
            setex=lambda key, ttl, value: setex_calls.append((key, ttl, value)),
            delete=lambda key: delete_calls.append(key),
        ),
    )
    monkeypatch.setattr(
        "internal.task.email_task.socket.getaddrinfo",
        lambda host, *_args, **_kwargs: [
            (socket.AF_INET6, 1, 6, "", ("240e:97c:2f:4::3f", 587, 0, 0)),
            (socket.AF_INET, 1, 6, "", ("183.47.101.192", 587)),
        ]
        if host == "smtp.qq.com"
        else [],
    )
    monkeypatch.setattr(
        "internal.service.email_service.EmailService.generate_verification_code",
        staticmethod(lambda length=6: "123456"),
    )

    from internal.task.email_task import send_verification_email_task

    send_verification_email_task.run(
        email="demo@example.com",
        scene="password_reset",
        client_ip="unknown",
    )

    assert send_servers == ["183.47.101.192"]
    assert timeout_values == [10]
    assert fake_mail.server == "smtp.qq.com"
    assert socket.getdefaulttimeout() is None
    assert len(setex_calls) == 3
    assert len(delete_calls) == 4


def test_send_verification_email_task_should_restore_previous_default_timeout(monkeypatch):
    send_servers = []
    setex_calls = []
    delete_calls = []

    def _fake_send(_msg):
        send_servers.append(fake_mail.server)

    fake_mail = SimpleNamespace(server="smtp.qq.com", send=_fake_send)
    injector = SimpleNamespace(get=lambda _cls: fake_mail)

    monkeypatch.setattr("app.http.app.injector", injector)
    monkeypatch.setattr(
        "internal.task.email_task.Message",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        "internal.task.email_task.current_app",
        SimpleNamespace(config={"MAIL_TIMEOUT": 10}),
    )
    monkeypatch.setattr(
        "internal.task.email_task.redis_client",
        SimpleNamespace(
            setex=lambda key, ttl, value: setex_calls.append((key, ttl, value)),
            delete=lambda key: delete_calls.append(key),
        ),
    )
    monkeypatch.setattr(
        "internal.task.email_task.socket.getaddrinfo",
        lambda host, *_args, **_kwargs: [
            (socket.AF_INET, 1, 6, "", ("183.47.101.192", 587)),
        ]
        if host == "smtp.qq.com"
        else [],
    )
    monkeypatch.setattr(
        "internal.service.email_service.EmailService.generate_verification_code",
        staticmethod(lambda length=6: "123456"),
    )

    from internal.task.email_task import send_verification_email_task

    socket.setdefaulttimeout(3)
    try:
        send_verification_email_task.run(
            email="demo@example.com",
            scene="password_reset",
            client_ip="unknown",
        )
        assert send_servers == ["183.47.101.192"]
        assert socket.getdefaulttimeout() == 3
        assert len(setex_calls) == 3
        assert len(delete_calls) == 4
    finally:
        socket.setdefaulttimeout(None)


def test_send_verification_email_task_should_fallback_to_original_server_when_dns_resolution_failed(monkeypatch):
    send_servers = []
    setex_calls = []
    delete_calls = []

    def _fake_send(_msg):
        send_servers.append(fake_mail.server)

    fake_mail = SimpleNamespace(server="smtp.qq.com", send=_fake_send)
    injector = SimpleNamespace(get=lambda _cls: fake_mail)

    monkeypatch.setattr("app.http.app.injector", injector)
    monkeypatch.setattr(
        "internal.task.email_task.Message",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        "internal.task.email_task.current_app",
        SimpleNamespace(config={"MAIL_TIMEOUT": 10}),
    )
    monkeypatch.setattr(
        "internal.task.email_task.redis_client",
        SimpleNamespace(
            setex=lambda key, ttl, value: setex_calls.append((key, ttl, value)),
            delete=lambda key: delete_calls.append(key),
        ),
    )
    monkeypatch.setattr(
        "internal.task.email_task.socket.getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(socket.gaierror("dns failed")),
    )
    monkeypatch.setattr(
        "internal.service.email_service.EmailService.generate_verification_code",
        staticmethod(lambda length=6: "123456"),
    )

    from internal.task.email_task import send_verification_email_task

    send_verification_email_task.run(
        email="demo@example.com",
        scene="password_reset",
        client_ip="unknown",
    )

    assert send_servers == ["smtp.qq.com"]
    assert fake_mail.server == "smtp.qq.com"
    assert len(setex_calls) == 3
    assert len(delete_calls) == 4


def test_send_verification_email_task_should_clear_pending_keys_when_send_failed(monkeypatch):
    fake_mail = SimpleNamespace(server="smtp.qq.com", send=lambda _msg: (_ for _ in ()).throw(RuntimeError("smtp down")))
    injector = SimpleNamespace(get=lambda _cls: fake_mail)
    setex_calls = []
    delete_calls = []

    monkeypatch.setattr("app.http.app.injector", injector)
    monkeypatch.setattr(
        "internal.task.email_task.Message",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        "internal.task.email_task.redis_client",
        SimpleNamespace(
            setex=lambda key, ttl, value: setex_calls.append((key, ttl, value)),
            delete=lambda key: delete_calls.append(key),
        ),
    )
    monkeypatch.setattr(
        "internal.service.email_service.EmailService.generate_verification_code",
        staticmethod(lambda length=6: "123456"),
    )

    from internal.task.email_task import send_verification_email_task

    try:
        send_verification_email_task.run(
            email="demo@example.com",
            scene="password_reset",
            client_ip="unknown",
        )
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert str(exc) == "smtp down"

    assert setex_calls == []
    assert delete_calls == [
        "password_reset:send_pending:demo@example.com",
        "password_reset:send_pending_ip:unknown",
    ]
