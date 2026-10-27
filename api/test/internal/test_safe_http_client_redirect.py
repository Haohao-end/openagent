from urllib.parse import urlsplit
from unittest.mock import Mock

import pytest
import requests

from internal.lib import safe_http_client as client


@pytest.mark.parametrize(
    "redirect_url,strip_credentials",
    [
        ("https://second.example/resource", True),
        ("https://first.example/next", False),
    ],
)
def test_redirect_does_not_leak_explicit_cookie_header_across_origins(monkeypatch, redirect_url, strip_credentials):
    initial = requests.Response()
    initial.status_code = 302
    initial.headers["Location"] = redirect_url
    final = requests.Response()
    final.status_code = 200

    session = Mock()
    session.request.side_effect = [initial, final]
    monkeypatch.setattr(client, "_build_session", lambda max_redirects: session)

    def validate(url):
        parsed = urlsplit(url)
        return client.SafeHttpTarget(
            original_url=url,
            scheme=parsed.scheme,
            hostname=parsed.hostname,
            ascii_hostname=parsed.hostname,
            port=None,
            resolved_ip="8.8.8.8",
        )

    monkeypatch.setattr(client, "_validate_safe_target", validate)

    response = client.safe_request(
        "GET",
        "https://first.example/start",
        headers={
            "Authorization": "Bearer test-secret",
            "Proxy-Authorization": "Basic proxy-secret",
            "Cookie": "session=test-secret",
            "X-Request-ID": "test-redirect",
        },
    )

    assert response is final
    assert session.request.call_count == 2
    first_headers = session.request.call_args_list[0].kwargs["headers"]
    next_headers = session.request.call_args_list[1].kwargs["headers"]
    assert first_headers["Cookie"] == "session=test-secret"
    assert next_headers["X-Request-ID"] == "test-redirect"
    assert ("Cookie" not in next_headers) is strip_credentials
    assert ("Authorization" not in next_headers) is strip_credentials
    assert ("Proxy-Authorization" not in next_headers) is strip_credentials
    initial.close()
    session.close.assert_called_once()
