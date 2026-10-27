import pytest

from internal.lib import safe_http_client


@pytest.mark.parametrize(
    "url,expected_host_header",
    [
        ("http://example.com:443/resource", "example.com:443"),
        ("https://example.com:80/resource", "example.com:80"),
        ("http://example.com:80/resource", "example.com"),
        ("https://example.com:443/resource", "example.com"),
    ],
)
def test_host_header_omits_only_the_scheme_default_port(monkeypatch, url, expected_host_header):
    monkeypatch.setattr(
        safe_http_client,
        "_resolve_host_ips",
        lambda *_args, **_kwargs: ["8.8.8.8"],
    )

    target = safe_http_client._validate_safe_target(url)

    assert target.host_header == expected_host_header
