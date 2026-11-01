from urllib.parse import urlsplit
from unittest.mock import Mock

import pytest
import requests

from internal.lib import safe_http_client as client


@pytest.mark.parametrize("redirect,strip_secrets", [
    ("https://other.example/target", True),
    ("https://source.example/next", False),
])
def test_raw_custom_auth_headers_stay_on_origin(monkeypatch, redirect, strip_secrets):
    first = requests.Response()
    first.status_code = 302
    first.headers["Location"] = redirect
    first.raw = Mock()
    last = requests.Response()
    last.status_code = 200
    session = Mock()
    session.request.side_effect = [first, last]
    monkeypatch.setattr(client, "_build_session", lambda max_redirects: session)

    def target(url):
        parts = urlsplit(url)
        return client.SafeHttpTarget(
            original_url=url, scheme=parts.scheme,
            hostname=parts.hostname, ascii_hostname=parts.hostname,
            port=None, resolved_ip="8.8.8.8",
        )

    monkeypatch.setattr(client, "_validate_safe_target", target)
    result = client.safe_request(
        "GET", "https://source.example/start", headers={
            "X-API-Key": "secret-key",
            "x-auth-token": "secret-token",
            "X-MCP-Token": "synthetic-mcp-token",
            "X-Request-ID": "trace-id",
        },
    )

    assert result is last
    forwarded = session.request.call_args_list[1].kwargs["headers"]
    assert forwarded["X-Request-ID"] == "trace-id"
    assert ("X-API-Key" not in forwarded) is strip_secrets
    assert ("x-auth-token" not in forwarded) is strip_secrets
    assert ("X-MCP-Token" not in forwarded) is strip_secrets
    session.close.assert_called_once()
