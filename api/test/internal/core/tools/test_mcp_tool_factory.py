import json
import pytest
import requests

from internal.core.tools.mcp_tools.providers.mcp_tool_factory import McpToolFactory, _parse_json_payload
from internal.exception import FailException


class _FakeResponse:
    def __init__(self, payload: dict):
        self.text = json.dumps(payload, ensure_ascii=False)
        self.headers = {}
        self.is_redirect = False

    def raise_for_status(self):
        return None


def test_mcp_tool_factory_should_list_remote_tools_and_call_selected_tool(monkeypatch):
    calls = []

    def _fake_safe_request(method, url, **kwargs):
        calls.append({
            "method": method,
            "url": url,
            "json": kwargs.get("json"),
            "headers": kwargs.get("headers"),
            "timeout": kwargs.get("timeout"),
            "allow_redirects": kwargs.get("allow_redirects"),
        })

        json = kwargs.get("json") or {}
        if json["method"] == "tools/list":
            return _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "tools": [
                            {
                                "name": "weather",
                                "description": "天气查询",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "city": {
                                            "type": "string",
                                            "description": "城市",
                                        },
                                        "days": {
                                            "type": "integer",
                                            "default": 1,
                                        },
                                    },
                                    "required": ["city"],
                                },
                            },
                            {
                                "name": "hidden_tool",
                                "description": "should be filtered",
                            },
                        ]
                    },
                }
            )

        if json["method"] == "tools/call":
            assert json["params"]["name"] == "weather"
            assert json["params"]["arguments"] == {"city": "杭州", "days": 1}
            return _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "content": [{"type": "text", "text": "杭州今天晴"}],
                    },
                }
            )

        raise AssertionError(f"unexpected method: {json['method']}")

    monkeypatch.setattr(
        "internal.core.tools.mcp_tools.providers.mcp_tool_factory.safe_request",
        _fake_safe_request,
    )

    factory = McpToolFactory()
    tools = factory.get_tools(
        [
            {
                "name": "weather_gateway",
                "description": "ModelScope weather",
                "transport": "streamable_http",
                "url": "https://mcp.example.com",
                "enabled": True,
                "headers": [
                    {"key": "Authorization", "value": "Bearer token"},
                ],
                "tool_names": ["weather"],
                "timeout_seconds": 15,
                "args": [],
                "env": {},
            }
        ]
    )

    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "mcp__weather_gateway__weather"

    result = tool.invoke({"city": "杭州"})
    result_text = result.content if hasattr(result, "content") else result

    assert result_text == "杭州今天晴"
    assert [call["json"]["method"] for call in calls] == ["tools/list", "tools/call"]
    assert [call["method"] for call in calls] == ["POST", "POST"]
    assert calls[0]["timeout"] == 15
    assert calls[0]["headers"]["Authorization"] == "Bearer token"


def test_mcp_tool_factory_should_parse_final_sse_event_after_progress(monkeypatch):
    def _fake_safe_request(_method, _url, **kwargs):
        response = _FakeResponse({})
        response.text = "\n\n".join(
            f"data: {json.dumps(event)}"
            for event in (
                {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progress": 1}},
                {"jsonrpc": "2.0", "id": kwargs["json"]["id"], "result": {"tools": [{"name": "weather"}]}},
            )
        )
        return response

    monkeypatch.setattr(
        "internal.core.tools.mcp_tools.providers.mcp_tool_factory.safe_request",
        _fake_safe_request,
    )

    tools = McpToolFactory()._list_remote_tools({"url": "https://mcp.example.com", "headers": []})

    assert tools == [{"name": "weather"}]


@pytest.mark.parametrize("response", [
    json.dumps({"jsonrpc": "2.0", "id": "other-request", "result": {"content": ["wrong"]}}),
    'data: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n'
    'data: {"jsonrpc":"2.0","id":"other-request","result":{"content":["wrong"]}}',
])
def test_mcp_tool_factory_should_reject_response_with_unmatched_request_id(response):
    with pytest.raises(FailException, match="匹配的MCP响应"):
        _parse_json_payload(response, expected_id="current-request")


def test_mcp_connection_error_should_not_expose_query_credentials(monkeypatch, caplog):
    sentinel = "SYNTHETIC_SENTINEL"

    class _Session:
        def request(self, _method, url, **kwargs):
            if kwargs["json"]["method"] == "tools/list":
                return _FakeResponse({
                    "jsonrpc": "2.0",
                    "id": kwargs["json"]["id"],
                    "result": {"tools": [{"name": "private_tool"}]},
                })
            raise requests.ConnectionError(f"connection failed for {url}")

        def close(self):
            pass

    monkeypatch.setattr("internal.lib.safe_http_client._build_session", lambda **_kwargs: _Session())
    tools = McpToolFactory().get_tools([{
        "name": "private_provider",
        "url": f"https://mcp.example.invalid/mcp?token={sentinel}",
        "enabled": True,
        "transport": "streamable_http",
    }])

    result = tools[0].invoke({})
    result_text = result.content if hasattr(result, "content") else result

    assert "失败" in result_text
    assert sentinel not in result_text
    assert sentinel not in caplog.text


def test_mcp_tool_factory_should_compile_complex_json_schema_and_keep_metadata(monkeypatch):
    complex_input_schema = {
        "type": "object",
        "properties": {
            "request": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["fast", "safe"],
                        "description": "运行模式",
                    },
                    "payload": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "string",
                                    "description": "ID",
                                },
                                "count": {
                                    "type": "integer",
                                    "default": 1,
                                },
                            },
                            "required": ["id"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["mode"],
                "additionalProperties": True,
            },
            "variant": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "integer"},
                ]
            },
            "when": {
                "type": "string",
                "format": "date",
                "description": "日期",
            },
        },
        "required": ["request"],
    }

    factory = McpToolFactory()
    captured_calls = []

    def _fake_call_remote_tool(binding, tool_name, arguments):
        captured_calls.append({
            "binding": binding,
            "tool_name": tool_name,
            "arguments": arguments,
        })
        assert tool_name == "complex_tool"
        assert arguments["request"]["mode"] == "fast"
        assert arguments["request"]["extra_flag"] == "keep"
        assert arguments["request"]["payload"][0]["count"] == 2
        assert arguments["variant"] == 3
        assert arguments["when"] == "2026-05-20"
        return "ok"

    monkeypatch.setattr(factory, "_call_remote_tool", _fake_call_remote_tool)

    tool = factory._build_langchain_tool(
        {
            "name": "complex_gateway",
            "description": "Complex MCP",
            "transport": "streamable_http",
            "url": "https://mcp.example.com",
            "enabled": True,
            "headers": [],
            "tool_names": ["complex_tool"],
            "timeout_seconds": 20,
            "args": [],
            "env": {},
        },
        {
            "name": "complex_tool",
            "title": "复杂工具",
            "description": "复杂输入结构的工具",
            "inputSchema": complex_input_schema,
            "outputSchema": {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                },
            },
            "annotations": {
                "readOnlyHint": True,
                "idempotentHint": True,
            },
        },
    )

    assert tool.name == "mcp__complex_gateway__complex_tool"
    assert "行为: 只读，幂等" in tool.description
    assert "输入:" in tool.description
    assert "request:对象参数" in tool.description
    assert "variant:string 或 integer" in tool.description
    assert tool.metadata["input_schema"] == complex_input_schema
    assert tool.metadata["output_schema"]["type"] == "object"
    assert tool.metadata["annotations"]["readOnlyHint"] is True
    assert tool.metadata["schema_summary"].startswith("对象参数:")
    assert tool.metadata["input_schema_summary"] == tool.metadata["schema_summary"]
    assert tool.metadata["output_schema_summary"].startswith("对象参数:")
    assert tool.metadata["annotations_summary"] == "只读，幂等"

    result = tool.invoke(
        {
            "request": {
                "mode": "fast",
                "extra_flag": "keep",
                "payload": [
                    {
                        "id": "item-1",
                        "count": 2,
                    }
                ],
            },
            "variant": 3,
            "when": "2026-05-20",
        }
    )
    result_text = result.content if hasattr(result, "content") else result

    assert result_text == "ok"
    assert len(captured_calls) == 1
    assert captured_calls[0]["arguments"]["request"]["extra_flag"] == "keep"


def test_mcp_tool_factory_should_prepare_and_refresh_binding_snapshots(monkeypatch):
    factory = McpToolFactory()
    binding = {
        "name": "weather_gateway",
        "description": "weather",
        "transport": "streamable_http",
        "url": "https://mcp.example.com",
        "enabled": True,
        "headers": [],
        "tool_names": ["weather"],
        "timeout_seconds": 15,
        "args": [],
        "env": {},
    }

    prepared = factory.prepare_binding_snapshots([binding])
    assert len(prepared) == 1
    assert prepared[0]["binding_identity"] == factory.build_binding_identity(binding)
    assert prepared[0]["status"] == "warming"
    assert prepared[0]["retryable"] is True

    tool_definitions = [
        {
            "name": "weather",
            "title": "天气查询",
            "description": "查询天气",
            "inputSchema": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
        }
    ]
    monkeypatch.setattr(factory, "_list_remote_tools", lambda _binding: tool_definitions)

    refreshed = factory.refresh_binding_snapshots([binding], prepared)

    assert len(refreshed) == 1
    assert refreshed[0]["status"] == "ready"
    assert refreshed[0]["retryable"] is False
    assert refreshed[0]["tool_names"] == ["weather"]
    assert refreshed[0]["tool_count"] == 1
    assert refreshed[0]["retry_count"] == 0
    assert refreshed[0]["binding_identity"] == factory.build_binding_identity(binding)


def test_mcp_tool_factory_should_build_tools_from_snapshots_without_live_discovery(monkeypatch):
    factory = McpToolFactory()
    binding = {
        "name": "weather_gateway",
        "description": "weather",
        "transport": "streamable_http",
        "url": "https://mcp.example.com",
        "enabled": True,
        "headers": [],
        "tool_names": ["weather"],
        "timeout_seconds": 15,
        "args": [],
        "env": {},
    }
    binding_identity = factory.build_binding_identity(binding)
    snapshots = [
        {
            "binding_identity": binding_identity,
            "binding_hash": "hash-1",
            "binding": binding,
            "status": "ready",
            "tool_definitions": [
                {
                    "name": "weather",
                    "title": "天气查询",
                    "description": "查询天气",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                }
            ],
            "tool_names": ["weather"],
            "tool_count": 1,
            "schema_hash": "schema-hash-1",
            "last_attempt_at": 1,
            "last_success_at": 1,
            "last_error": "",
            "retry_count": 0,
            "retryable": False,
        }
    ]

    def _raise_if_called(_binding):
        raise AssertionError("live discovery should not be called when snapshots are provided")

    monkeypatch.setattr(factory, "_list_remote_tools", _raise_if_called)

    tools = factory.get_tools([binding], snapshots)

    assert len(tools) == 1
    assert tools[0].name == "mcp__weather_gateway__weather"
    assert tools[0].metadata["binding_name"] == "weather_gateway"
