import pytest

from internal.exception import ValidateErrorException
from internal.lib import safe_http_client


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@example.com/image.png",
        "https://user@example.com/image.png",
        "https://:password@example.com/image.png",
    ],
)
def test_validate_safe_http_url_rejects_embedded_credentials(monkeypatch, url):
    def unexpected_dns(*_args, **_kwargs):
        raise AssertionError("DNS must not run for URLs with embedded credentials")

    monkeypatch.setattr(safe_http_client, "_resolve_host_ips", unexpected_dns)

    with pytest.raises(ValidateErrorException, match="URL不能包含用户名或密码"):
        safe_http_client.validate_safe_http_url(url)


def test_validate_safe_http_url_accepts_public_url_without_userinfo(monkeypatch):
    monkeypatch.setattr(
        safe_http_client,
        "_resolve_host_ips",
        lambda *_args, **_kwargs: ["8.8.8.8"],
    )
    assert safe_http_client.validate_safe_http_url(
        "https://example.com/image.png"
    ) == "https://example.com/image.png"
