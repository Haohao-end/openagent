import pytest

from config import Config


def test_config_should_include_mail_timeout_in_seconds(monkeypatch):
    monkeypatch.setenv("MAIL_TIMEOUT", "10")

    conf = Config()

    assert conf.MAIL_TIMEOUT == 10


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("invalid", False),
    ],
)
def test_config_should_parse_boolean_env_values_robustly(monkeypatch, value, expected):
    monkeypatch.setenv("MAIL_USE_TLS", value)

    conf = Config()

    assert conf.MAIL_USE_TLS is expected


def test_config_should_build_redis_urls_without_empty_credentials(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "redis.local")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_DB", "2")
    monkeypatch.setenv("REDIS_USERNAME", "")
    monkeypatch.setenv("REDIS_PASSWORD", "")
    monkeypatch.setenv("REDIS_USE_SSL", "false")
    monkeypatch.setenv("CELERY_BROKER_DB", "5")
    monkeypatch.setenv("CELERY_RESULT_BACKEND_DB", "6")

    conf = Config()

    assert conf.REDIS_URL == "redis://redis.local:6380/2"
    assert conf.CELERY["broker_url"] == "redis://redis.local:6380/5"
    assert conf.CELERY["result_backend"] == "redis://redis.local:6380/6"


def test_config_should_build_rediss_urls_with_password_only(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "secure-redis.local")
    monkeypatch.setenv("REDIS_PORT", "6381")
    monkeypatch.setenv("REDIS_DB", "4")
    monkeypatch.setenv("REDIS_USERNAME", "")
    monkeypatch.setenv("REDIS_PASSWORD", "secret")
    monkeypatch.setenv("REDIS_USE_SSL", "1")
    monkeypatch.setenv("CELERY_BROKER_DB", "7")
    monkeypatch.setenv("CELERY_RESULT_BACKEND_DB", "8")

    conf = Config()

    assert conf.REDIS_URL == "rediss://:secret@secure-redis.local:6381/4"
    assert conf.CELERY["broker_url"] == "rediss://:secret@secure-redis.local:6381/7"
    assert conf.CELERY["result_backend"] == "rediss://:secret@secure-redis.local:6381/8"
