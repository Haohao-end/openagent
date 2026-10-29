from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import ProgrammingError

from internal.exception import ValidateErrorException
from internal.service.mcp_service import McpService


@contextmanager
def _null_context():
    yield


def _field(value):
    return SimpleNamespace(data=value)


def _req(*, current_page=1, page_size=20, search_word="", category=""):
    return SimpleNamespace(
        current_page=_field(current_page),
        page_size=_field(page_size),
        search_word=_field(search_word),
        category=_field(category),
    )


def _build_catalog_provider():
    return SimpleNamespace(
            name="weather_gateway",
            provider_entity=SimpleNamespace(
                name="weather_gateway",
                label="天气 MCP",
                description="提供天气查询",
                icon="",
                background="#DBEAFE",
                category="productivity",
                transport="streamable_http",
                url="https://mcp.example.com",
                command="",
            headers=[],
            tool_names=[],
            args=[],
            env={},
            timeout_seconds=30,
            source_type="catalog",
            source_key="@modelscope/weather_gateway",
            source_url="https://www.modelscope.cn/mcp/servers/@modelscope/weather_gateway",
            created_at=1744848000,
            is_public=True,
        ),
    )


def _build_service(*, table_exists: bool, stub_catalog_payload: bool = True):
    catalog_provider = _build_catalog_provider()
    db = SimpleNamespace(
        session=SimpleNamespace(
            query=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected db query")),
        ),
        auto_commit=_null_context,
    )
    service = McpService(
        db=db,
        mcp_provider_manager=SimpleNamespace(
            get_providers=lambda: [catalog_provider],
            get_provider=lambda provider_name: catalog_provider if provider_name == catalog_provider.name else None,
        ),
        icon_generator_service=SimpleNamespace(generate_icon=lambda *_args, **_kwargs: "icon"),
    )
    service._has_mcp_provider_table = lambda: table_exists  # type: ignore[method-assign]
    if stub_catalog_payload:
        service._build_catalog_provider_payload = lambda _catalog_provider, include_tools=False: {
            "provider_key": "catalog::weather_gateway",
            "provider_id": "catalog::weather_gateway",
            "name": "weather_gateway",
            "label": "天气 MCP",
            "icon": "",
            "background": "#DBEAFE",
            "description": "提供天气查询",
            "category": "productivity",
            "transport": "streamable_http",
            "url": "https://mcp.example.com",
            "command": "",
            "headers": [],
            "tool_names": [],
            "args": [],
            "env": {},
            "timeout_seconds": 30,
            "source_type": "catalog",
            "source_key": "@modelscope/weather_gateway",
            "source_url": "https://www.modelscope.cn/mcp/servers/@modelscope/weather_gateway",
            "creator_name": "ModelScope",
            "creator_avatar": "",
            "is_public": True,
            "is_bindable": True,
            "bind_reason": "",
            "published_at": 1744848000,
            "created_at": 1744848000,
            "updated_at": 1744848000,
            "tool_count": 0,
            "tools": [],
            "binding": {
                "name": "weather_gateway",
                "description": "提供天气查询",
                "transport": "streamable_http",
                "url": "https://mcp.example.com",
                "command": "",
                "enabled": True,
                "headers": [],
                "tool_names": [],
                "args": [],
                "env": {},
                "provider_key": "catalog::weather_gateway",
                "source_type": "catalog",
                "source_key": "@modelscope/weather_gateway",
                "source_url": "https://www.modelscope.cn/mcp/servers/@modelscope/weather_gateway",
                "label": "天气 MCP",
                "icon": "",
                "category": "productivity",
            },
        }
    return service


def test_get_public_mcp_providers_with_page_should_fallback_to_catalog_when_table_missing():
    service = _build_service(table_exists=False)

    providers, paginator = service.get_public_mcp_providers_with_page(_req(page_size=20))

    assert len(providers) == 1
    assert providers[0]["name"] == "weather_gateway"
    assert paginator.total_record == 1
    assert paginator.total_page == 1


@pytest.mark.parametrize((
    "is_public", "expected_headers", "expected_env", "expected_url", "expected_command", "expected_args",
), [
    (True, [], {}, "https://mcp.example.com/mcp?version=1", "", []),
    (
        False,
        [{"key": "Authorization", "value": "Bearer test-secret"}],
        {"API_TOKEN": "test-secret"},
        "https://mcp-user:test-secret@mcp.example.com/mcp?access_token=test-secret&x-api-key=SYNTHETIC_SENTINEL&version=1",
        "node server.js --token=test-secret",
        ["--token", "test-secret"],
    ),
])
def test_provider_payload_only_exposes_credentials_for_private_providers(
    is_public, expected_headers, expected_env, expected_url, expected_command, expected_args
):
    service = _build_service(table_exists=False, stub_catalog_payload=False)
    source_url = "https://source-user:test-secret@repo.example.com/source?token=test-secret&x-api-key=SYNTHETIC_SENTINEL&version=1"
    expected_source_url = source_url if not is_public else "https://repo.example.com/source?version=1"

    payload = service._build_provider_payload(
        provider_key="provider-key",
        provider_id="provider-id",
        name="test-provider",
        label="Test Provider",
        icon="",
        description="",
        category="",
        transport="streamable_http",
        url="https://mcp-user:test-secret@mcp.example.com/mcp?access_token=test-secret&x-api-key=SYNTHETIC_SENTINEL&version=1",
        command="node server.js --token=test-secret",
        headers=[{"key": "Authorization", "value": "Bearer test-secret"}],
        tool_names=[],
        args=["--token", "test-secret"],
        env={"API_TOKEN": "test-secret"},
        timeout_seconds=30,
        source_type="custom",
        source_key="provider-key",
        source_url=source_url,
        is_public=is_public,
    )

    assert payload["headers"] == expected_headers
    assert payload["env"] == expected_env
    assert payload["url"] == expected_url
    assert payload["command"] == expected_command
    assert payload["args"] == expected_args
    assert payload["source_url"] == expected_source_url
    assert payload["binding"]["headers"] == expected_headers
    assert payload["binding"]["env"] == expected_env
    assert payload["binding"]["url"] == expected_url
    assert payload["binding"]["command"] == expected_command
    assert payload["binding"]["args"] == expected_args
    assert payload["binding"]["source_url"] == expected_source_url


def test_get_public_mcp_provider_should_reject_invalid_catalog_key_encoding():
    service = _build_service(table_exists=False)

    with pytest.raises(ValidateErrorException, match="MCP provider key 格式无效"):
        service.get_public_mcp_provider("catalog::wA")


def test_get_mcp_providers_with_page_should_return_empty_when_table_missing():
    service = _build_service(table_exists=False)

    providers, paginator = service.get_mcp_providers_with_page(_req(page_size=20), SimpleNamespace(id="account"))

    assert providers == []
    assert paginator.total_record == 0
    assert paginator.total_page == 0


def test_get_public_mcp_providers_with_page_should_support_catalog_integer_timestamps():
    service = _build_service(table_exists=False, stub_catalog_payload=False)

    providers, paginator = service.get_public_mcp_providers_with_page(_req(page_size=20))

    assert len(providers) == 1
    assert providers[0]["published_at"] == 1744848000
    assert providers[0]["created_at"] == 1744848000
    assert paginator.total_record == 1
    assert paginator.total_page == 1


def test_get_mcp_providers_with_page_should_return_empty_when_paginate_raises_missing_table():
    service = _build_service(table_exists=True)

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def paginate(self, *_args, **_kwargs):
            raise ProgrammingError("select 1", {}, SimpleNamespace(pgcode="42P01"))

    service.db.session = SimpleNamespace(query=lambda *_args, **_kwargs: _Query())

    providers, paginator = service.get_mcp_providers_with_page(_req(page_size=20), SimpleNamespace(id="account"))

    assert providers == []
    assert paginator.total_record == 0
    assert paginator.total_page == 0
