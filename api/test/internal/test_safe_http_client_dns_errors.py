import socket

import pytest

from internal.exception import ValidateErrorException
from internal.lib import safe_http_client


@pytest.mark.parametrize("error", [
    socket.gaierror(-2, "Name or service not known"),
    TimeoutError("DNS resolver timed out"),
    OSError("temporary resolver failure"),
])
def test_dns_failures_are_consistent_validation_errors(monkeypatch, error):
    def fail_resolution(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(safe_http_client.socket, "getaddrinfo", fail_resolution)
    with pytest.raises(ValidateErrorException, match="URL主机名无法解析"):
        safe_http_client.validate_safe_http_url("https://unresolved.example/resource")
