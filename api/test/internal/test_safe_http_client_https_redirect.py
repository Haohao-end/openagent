from urllib.parse import urlsplit
from unittest.mock import Mock

import pytest
import requests

from internal.exception import ValidateErrorException
from internal.lib import safe_http_client as client


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_https_redirect_must_not_downgrade_to_http(monkeypatch, status):
    first = requests.Response()
    first.status_code = status
    first.headers["Location"] = "http://example.com/insecure"
    first.raw = Mock()
    session = Mock()
    session.request.return_value = first
    monkeypatch.setattr(client, "_build_session", lambda max_redirects: session)
    validated = []

    def validate(url):
        validated.append(url)
        parts = urlsplit(url)
        return client.SafeHttpTarget(
            original_url=url, scheme=parts.scheme,
            hostname=parts.hostname, ascii_hostname=parts.hostname,
            port=None, resolved_ip="8.8.8.8",
        )

    monkeypatch.setattr(client, "_validate_safe_target", validate)
    with pytest.raises(ValidateErrorException, match="禁止HTTPS降级重定向"):
        client.safe_request("GET", "https://example.com/start")

    assert validated == ["https://example.com/start"]
    session.request.assert_called_once()
    session.close.assert_called_once()
    assert first.raw.close.call_count == 1
