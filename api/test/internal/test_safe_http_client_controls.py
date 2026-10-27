import pytest

from internal.exception import ValidateErrorException
from internal.lib import safe_http_client


@pytest.mark.parametrize("url", [
    "https://example.com/hello\\nworld".replace("\\n", "\n"),
    "https://example.com/hello\\rworld".replace("\\r", "\r"),
    "https://example.com/hello\\tworld".replace("\\t", "\t"),
    "https://example.com/hello" + chr(0) + "world",
    "https://example.com/hello" + chr(127) + "world",
])
def test_url_with_embedded_controls_is_rejected_before_dns(monkeypatch, url):
    def forbid_dns(*_args, **_kwargs):
        raise AssertionError("DNS must not run for control characters")

    monkeypatch.setattr(safe_http_client, "_resolve_host_ips", forbid_dns)
    with pytest.raises(ValidateErrorException, match="非法控制字符"):
        safe_http_client.validate_safe_http_url(url)
