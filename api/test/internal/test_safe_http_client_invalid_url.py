import pytest

from internal.exception import ValidateErrorException
from internal.lib import safe_http_client


@pytest.mark.parametrize("url", [
    "https://[2001:db8::1",
    "http://[not-an-ip]/path",
    "https://[::1/path",
])
def test_malformed_bracketed_urls_raise_validation_error_before_dns(monkeypatch, url):
    def unexpected_dns(*_args, **_kwargs):
        raise AssertionError("DNS must not run for malformed URLs")

    monkeypatch.setattr(safe_http_client, "_resolve_host_ips", unexpected_dns)

    with pytest.raises(ValidateErrorException, match="URL格式无效"):
        safe_http_client.validate_safe_http_url(url)
