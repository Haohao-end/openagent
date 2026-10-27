import pytest

from internal.exception import ValidateErrorException
from internal.lib import safe_http_client


@pytest.mark.parametrize("url", [
    "\nhttps://example.com/path",
    "https://example.com/path\r",
    "\thttps://example.com/path",
    "https://example.com/path\x7f",
])
def test_leading_or_trailing_url_controls_are_rejected_before_dns(monkeypatch, url):
    def forbid_dns(*_args, **_kwargs):
        raise AssertionError("DNS must not run for invalid URLs")

    monkeypatch.setattr(safe_http_client, "_resolve_host_ips", forbid_dns)
    with pytest.raises(ValidateErrorException, match="非法控制字符"):
        safe_http_client.validate_safe_http_url(url)


def test_harmless_spaces_around_url_are_still_trimmed(monkeypatch):
    monkeypatch.setattr(
        safe_http_client, "_resolve_host_ips",
        lambda *_args, **_kwargs: ["8.8.8.8"],
    )
    assert safe_http_client.validate_safe_http_url("  https://example.com/path  ") == (
        "https://example.com/path"
    )
