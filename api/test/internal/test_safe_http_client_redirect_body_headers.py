from urllib.parse import urlsplit
from unittest.mock import Mock

import pytest
import requests

from internal.lib import safe_http_client as client


@pytest.mark.parametrize("status,expect_get", [
    (301, True), (302, True), (303, True), (307, False), (308, False),
])
def test_redirect_removes_body_headers_only_when_switching_to_get(monkeypatch, status, expect_get):
    first = requests.Response()
    first.status_code = status
    first.headers["Location"] = "/next"
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
    response = client.safe_request(
        "POST", "https://example.com/start", data="payload",
        headers={
            "Content-Type": "application/json",
            "Content-Length": "7",
            "Transfer-Encoding": "chunked",
            "X-Request-ID": "keep",
        },
    )

    assert response is last
    sent = session.request.call_args_list[1]
    assert sent.args[0] == ("GET" if expect_get else "POST")
    assert sent.kwargs["data"] == (None if expect_get else "payload")
    assert sent.kwargs["headers"]["X-Request-ID"] == "keep"
    for key in ("Content-Type", "Content-Length", "Transfer-Encoding"):
        assert (key not in sent.kwargs["headers"]) is expect_get
    session.close.assert_called_once()
