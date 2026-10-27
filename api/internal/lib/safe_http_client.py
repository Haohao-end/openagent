from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter

from internal.exception import FailException, ValidateErrorException


DEFAULT_SAFE_HTTP_TIMEOUT_SECONDS = 30
DEFAULT_SAFE_HTTP_MAX_REDIRECTS = 3
_ALLOWED_SCHEMES = {"http", "https"}
_DEFAULT_HTTP_PORT = 80
_DEFAULT_HTTPS_PORT = 443


@dataclass(frozen=True)
class SafeHttpTarget:
    """已经完成 SSRF 检查的目标 URL 信息。"""

    original_url: str
    scheme: str
    hostname: str
    ascii_hostname: str
    port: int | None
    resolved_ip: str

    @property
    def host_header(self) -> str:
        host = self.ascii_hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"

        if self.port is None:
            return host
        return f"{host}:{self.port}"

    @property
    def host_header_name(self) -> str:
        return self.ascii_hostname


def _normalize_raw_url(url: Any) -> str:
    normalized = str(url or "").strip()
    if not normalized:
        raise ValidateErrorException("URL不能为空")
    return normalized


def _normalize_hostname(hostname: str) -> str:
    normalized = str(hostname or "").strip().rstrip(".")
    if not normalized:
        raise ValidateErrorException("URL必须包含主机名")

    lowered = normalized.lower()
    if lowered == "localhost" or lowered.endswith(".localhost"):
        raise ValidateErrorException("不允许访问本地hostname")

    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        try:
            ascii_hostname = normalized.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValidateErrorException("URL中的主机名无效") from exc
        if not ascii_hostname:
            raise ValidateErrorException("URL必须包含主机名")
        return ascii_hostname.lower()

    return normalized


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    if ip.is_unspecified:
        return True
    if ip.is_loopback:
        return True
    if ip.is_link_local:
        return True
    if ip.is_multicast:
        return True
    if ip.is_private:
        return True
    if ip.is_reserved:
        return True
    if not ip.is_global:
        return True
    return False


def _resolve_host_ips(hostname: str, port: int | None) -> list[str]:
    try:
        address_infos = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValidateErrorException("URL主机名无法解析") from exc

    resolved_ips: list[str] = []
    seen: set[str] = set()
    for family, _socktype, _proto, _canonname, sockaddr in address_infos:
        if family == socket.AF_INET:
            raw_ip = sockaddr[0]
        elif family == socket.AF_INET6:
            raw_ip = sockaddr[0]
        else:
            continue

        ip = ipaddress.ip_address(raw_ip)
        ip_str = str(ip)
        if ip_str not in seen:
            seen.add(ip_str)
            resolved_ips.append(ip_str)

    if not resolved_ips:
        raise ValidateErrorException("URL主机名无法解析到有效IP")

    blocked_ips = [ip for ip in resolved_ips if _is_blocked_ip(ipaddress.ip_address(ip))]
    if blocked_ips:
        raise ValidateErrorException(f"URL解析到不允许的地址: {', '.join(blocked_ips)}")

    return resolved_ips


def _validate_safe_target(url: Any) -> SafeHttpTarget:
    normalized_url = _normalize_raw_url(url)
    parsed = urlsplit(normalized_url)

    if not parsed.scheme or parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValidateErrorException("URL必须是绝对的http或https地址")

    if parsed.username is not None or parsed.password is not None:
        raise ValidateErrorException("URL不能包含用户名或密码")

    hostname = parsed.hostname
    if not hostname:
        raise ValidateErrorException("URL必须包含主机名")

    ascii_hostname = _normalize_hostname(hostname)

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValidateErrorException("URL端口格式无效") from exc

    if port is None:
        port = _DEFAULT_HTTPS_PORT if parsed.scheme.lower() == "https" else _DEFAULT_HTTP_PORT

    resolved_ips = _resolve_host_ips(ascii_hostname, port)

    # 选择第一个合法IP并用于连接 pinning。
    return SafeHttpTarget(
        original_url=normalized_url,
        scheme=parsed.scheme.lower(),
        hostname=ascii_hostname,
        ascii_hostname=ascii_hostname,
        port=port if port != (_DEFAULT_HTTPS_PORT if parsed.scheme.lower() == "https" else _DEFAULT_HTTP_PORT) else None,
        resolved_ip=resolved_ips[0],
    )


def validate_safe_http_url(url: Any) -> str:
    """校验一个 URL 是否允许作为出站请求目标。"""
    target = _validate_safe_target(url)
    return target.original_url


def _origin_tuple(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is None:
        port = _DEFAULT_HTTPS_PORT if parsed.scheme.lower() == "https" else _DEFAULT_HTTP_PORT
    return parsed.scheme.lower(), hostname.lower(), port


def _should_strip_sensitive_headers(previous_url: str, next_url: str) -> bool:
    return _origin_tuple(previous_url) != _origin_tuple(next_url)


class _PinnedAddressHTTPAdapter(HTTPAdapter):
    """把连接锚定到已验证的解析 IP，同时保留原始 Host / TLS SNI。"""

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        target = _validate_safe_target(request.url)
        host_params, pool_kwargs = self.build_connection_pool_key_attributes(request, verify, cert)
        host_params = dict(host_params)
        pool_kwargs = dict(pool_kwargs)

        if "host" not in host_params:
            raise ValidateErrorException("URL主机名无法解析")

        request.headers["Host"] = target.host_header
        host_params["host"] = target.resolved_ip

        if target.scheme == "https":
            pool_kwargs["server_hostname"] = target.hostname
            pool_kwargs["assert_hostname"] = target.hostname
        else:
            pool_kwargs.pop("server_hostname", None)
            pool_kwargs.pop("assert_hostname", None)

        return self.poolmanager.connection_from_host(**host_params, pool_kwargs=pool_kwargs)


def _build_session(max_redirects: int) -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.max_redirects = max_redirects
    adapter = _PinnedAddressHTTPAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def safe_request(
    method: str,
    url: Any,
    *,
    params: Any = None,
    json: Any = None,
    data: Any = None,
    headers: dict[str, Any] | None = None,
    cookies: Any = None,
    timeout: int | float | tuple[int | float, int | float] = DEFAULT_SAFE_HTTP_TIMEOUT_SECONDS,
    allow_redirects: bool = True,
    max_redirects: int = DEFAULT_SAFE_HTTP_MAX_REDIRECTS,
    verify: bool | str = True,
    cert: Any = None,
    stream: bool = False,
    auth: Any = None,
) -> requests.Response:
    """发起经过 SSRF 防护的 HTTP 请求。"""
    current_target = _validate_safe_target(url)
    current_method = str(method or "").strip().upper()
    if not current_method:
        raise ValidateErrorException("HTTP请求方法不能为空")

    current_url = current_target.original_url
    current_params = params
    current_json = json
    current_data = data
    current_headers = dict(headers or {})
    current_cookies = cookies
    current_auth = auth
    redirects_remaining = max_redirects

    session = _build_session(max_redirects=max_redirects)
    try:
        while True:
            try:
                response = session.request(
                    current_method,
                    current_url,
                    params=current_params,
                    json=current_json,
                    data=current_data,
                    headers=current_headers,
                    cookies=current_cookies,
                    timeout=timeout,
                    allow_redirects=False,
                    verify=verify,
                    cert=cert,
                    stream=stream,
                    auth=current_auth,
                )
            except ValidateErrorException:
                raise
            except requests.exceptions.Timeout as exc:
                raise FailException("HTTP请求超时") from exc
            except requests.exceptions.RequestException as exc:
                raise FailException(f"HTTP请求失败: {exc}") from exc

            if not allow_redirects or not response.is_redirect:
                return response

            location = response.headers.get("Location")
            if not location:
                return response

            if redirects_remaining <= 0:
                response.close()
                raise FailException("URL重定向次数超过限制")

            try:
                next_url = urljoin(current_url, location)
                next_target = _validate_safe_target(next_url)
            except Exception:
                response.close()
                raise

            if _should_strip_sensitive_headers(current_url, next_target.original_url):
                current_headers = {
                    key: value
                    for key, value in current_headers.items()
                    if key.lower() not in {"authorization", "proxy-authorization", "cookie"}
                }
                current_cookies = None
                current_auth = None

            previous_method = current_method
            if response.status_code == 303:
                if current_method != "HEAD":
                    current_method = "GET"
                    current_data = None
                    current_json = None
            elif response.status_code in (301, 302):
                if current_method not in {"GET", "HEAD"}:
                    current_method = "GET"
                    current_data = None
                    current_json = None

            if current_method == "GET" and previous_method not in {"GET", "HEAD"}:
                current_headers = {
                    key: value for key, value in current_headers.items()
                    if key.lower() not in {"content-type", "content-length", "transfer-encoding"}
                }

            if current_method == "GET" or current_method == "HEAD":
                current_data = None
                current_json = None

            current_url = next_target.original_url
            current_params = None
            redirects_remaining -= 1
            response.close()
    finally:
        session.close()
