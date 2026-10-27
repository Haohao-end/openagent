from urllib.parse import urlsplit
from unittest.mock import Mock

import pytest
import requests

from internal.exception import ValidateErrorException
from internal.lib import safe_http_client as client


@pytest.mark.parametrize("status", [307, 308])
def test_cross_origin_body_replay_is_rejected_before_second_request(monkeypatch, status):
    first = requests.Response()
    first.status_code = status
    first.headers["Location"] = "https://other.example/receive"
    first.raw = Mock()

    session = Mock()
    session.request.return_value = first
    monkeypatch.setattr(client, "_build_session", lambda max_redirects: session)

    def target(url):
        parsed = urlsplit(url)
        return client.SafeHttpTarget(
            original_url=url, scheme=parsed.scheme,
            hostname=parsed.hostname, ascii_hostname=parsed.hostname,
            port=None, resolved_ip="8.8.8.8",
        )

    monkeypatch.setattr(client, "_validate_safe_target", target)

    with pytest.raises(ValidateErrorException, match="禁止跨域重定向转发请求体"):
        client.safe_request("POST", "https://source.example/start", json={"secret": "value"})

    session.request.assert_called_once()
    first.raw.close.assert_called_once()
    session.close.assert_called_once()


@pytest.mark.parametrize("redirect,allowed", [
    ("https://source.example/next", True),
    ("https://other.example/next", False),
])
def test_bodyless_redirect_stays_allowed_across_origins(monkeypatch, redirect, allowed):
    first = requests.Response()
    first.status_code = 307
    first.headers["Location"] = redirect
    first.raw = Mock()
    last = requests.Response()
    last.status_code = 200
    session = Mock()
    session.request.side_effect = [first, last]
    monkeypatch.setattr(client, "_build_session", lambda max_redirects: session)

    def target(url):
        parsed = urlsplit(url)
        return client.SafeHttpTarget(
            original_url=url, scheme=parsed.scheme,
            hostname=parsed.hostname, ascii_hostname=parsed.hostname,
            port=None, resolved_ip="8.8.8.8",
        )

    monkeypatch.setattr(client, "_validate_safe_target", target)

    assert client.safe_request("POST" if allowed else "GET", "https://source.example/start", data="payload" if allowed else None) is last
    assert session.request.call_count == 2
    session.close.assert_called_once()
