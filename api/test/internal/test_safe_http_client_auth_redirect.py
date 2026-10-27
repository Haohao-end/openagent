from urllib.parse import urlsplit
from unittest.mock import Mock

import pytest
import requests

from internal.lib import safe_http_client as client


@pytest.mark.parametrize("location,drop_auth", [
    ("https://different.example/target", True),
    ("https://source.example/next", False),
])
def test_redirect_strips_auth_argument_only_when_origin_changes(monkeypatch, location, drop_auth):
    first = requests.Response()
    first.status_code = 302
    first.headers["Location"] = location
    first.raw = Mock()
    second = requests.Response()
    second.status_code = 200

    fake = Mock()
    fake.request.side_effect = [first, second]
    monkeypatch.setattr(client, "_build_session", lambda max_redirects: fake)

    def target(url):
        parsed = urlsplit(url)
        return client.SafeHttpTarget(
            original_url=url,
            scheme=parsed.scheme,
            hostname=parsed.hostname,
            ascii_hostname=parsed.hostname,
            port=None,
            resolved_ip="8.8.8.8",
        )

    monkeypatch.setattr(client, "_validate_safe_target", target)
    credential = ("developer", "example-pass")
    result = client.safe_request("GET", "https://source.example/start", auth=credential)

    assert result is second
    assert fake.request.call_count == 2
    assert fake.request.call_args_list[0].kwargs["auth"] == credential
    assert (fake.request.call_args_list[1].kwargs["auth"] is None) is drop_auth
    fake.close.assert_called_once()
