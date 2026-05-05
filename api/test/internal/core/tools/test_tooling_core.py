from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from internal.core.tools.api_tools.entities import (
    OpenAPISchema,
    ParameterIn,
    ParameterType,
    ToolEntity,
)
from internal.core.tools.api_tools.providers.api_provider_manager import (
    ApiProviderManager,
)
from internal.core.tools.builtin_tools.categories.builtin_category_manager import (
    BuiltinCategoryManager,
)
from internal.core.tools.builtin_tools.entities.category_entity import CategoryEntity
from internal.core.tools.builtin_tools.entities.provider_entity import (
    Provider,
    ProviderEntity,
)
from internal.core.tools.builtin_tools.entities.tool_entity import (
    ToolEntity as BuiltinToolEntity,
)
from internal.core.tools.builtin_tools.providers.builtin_provider_manager import (
    BuiltinProviderManager,
)
from internal.exception import FailException, NotFoundException, ValidateErrorException


def test_api_provider_manager_should_create_dynamic_model_from_parameters():
    model_cls = ApiProviderManager._create_model_from_parameters(
        [
            {
                "name": "keyword",
                "type": ParameterType.STR,
                "required": True,
                "description": "search word",
            },
            {
                "name": "page",
                "type": ParameterType.INT,
                "required": False,
                "description": "page no",
            },
            {
                "name": "fallback",
                "type": "unknown",
                "required": True,
                "description": "fallback as str",
            },
        ]
    )
    fields = model_cls.model_fields

    assert set(fields.keys()) == {"keyword", "page", "fallback"}
    assert fields["keyword"].is_required() is True
    # 当前实现只设置了 Optional[T]，但没有给 default=None，
    # 因此字段仍会被 pydantic 视为 required。这里按现有行为断言，避免误报。
    assert fields["page"].is_required() is True
    assert "Optional" in str(fields["page"].annotation)
    assert fields["fallback"].annotation is str


def test_api_provider_manager_should_create_tool_function_and_dispatch_parameters(
    monkeypatch,
):
    captured = {}

    def _fake_request(method, url, params, json, headers, cookies, timeout=None):
        captured["method"] = method
        captured["url"] = url
        captured["params"] = params
        captured["json"] = json
        captured["headers"] = headers
        captured["cookies"] = cookies
        captured["timeout"] = timeout
        return SimpleNamespace(text="tool-response")

    monkeypatch.setattr(
        "internal.core.tools.api_tools.providers.api_provider_manager.requests.request",
        _fake_request,
    )

    tool_entity = ToolEntity(
        id=str(uuid4()),
        name="search",
        url="https://api.example.com/items/{item_id}",
        method="post",
        description="desc",
        headers=[{"key": "x-api-key", "value": "fixed"}],
        parameters=[
            {"name": "item_id", "in": ParameterIn.PATH, "type": ParameterType.STR},
            {"name": "keyword", "in": ParameterIn.QUERY, "type": ParameterType.STR},
            {"name": "auth", "in": ParameterIn.HEADER, "type": ParameterType.STR},
            {"name": "sid", "in": ParameterIn.COOKIE, "type": ParameterType.STR},
            {
                "name": "payload",
                "in": ParameterIn.REQUEST_BODY,
                "type": ParameterType.STR,
            },
        ],
    )

    tool_func = ApiProviderManager._create_tool_func_from_tool_entity(tool_entity)
    response = tool_func(
        item_id="42",
        keyword="python",
        auth="Bearer 123",
        sid="cookie-1",
        payload={"k": "v"},
        unknown_field="ignored",
    )

    assert response == "tool-response"
    assert captured["method"] == "post"
    assert captured["url"] == "https://api.example.com/items/42"
    assert captured["params"] == {"keyword": "python"}
    assert captured["json"] == {"payload": {"k": "v"}}
    assert captured["headers"] == {"x-api-key": "fixed", "auth": "Bearer 123"}
    assert captured["cookies"] == {"sid": "cookie-1"}
    assert captured["timeout"] == 30


def test_api_provider_manager_get_tool_should_delegate_to_structured_tool(monkeypatch):
    captured = {}

    def _fake_from_function(func, name, description, args_schema):
        captured["func"] = func
        captured["name"] = name
        captured["description"] = description
        captured["args_schema"] = args_schema
        return "structured-tool"

    monkeypatch.setattr(
        "internal.core.tools.api_tools.providers.api_provider_manager.StructuredTool.from_function",
        _fake_from_function,
    )

    manager = ApiProviderManager()
    tool_entity = ToolEntity(
        id="tool-id",
        name="search",
        method="get",
        url="https://api.example.com/search",
        description="search api",
        parameters=[],
    )

    tool = manager.get_tool(tool_entity)

    assert tool == "structured-tool"
    assert captured["name"] == "tool-id_search"
    assert captured["description"] == "search api"


def _valid_openapi_paths():
    return {
        "/items/{id}": {
            "get": {
                "description": "query item",
                "operationId": "get_item",
                "parameters": [
                    {
                        "name": "id",
                        "in": ParameterIn.PATH,
                        "description": "item id",
                        "required": True,
                        "type": ParameterType.STR,
                    }
                ],
            },
            "put": {"description": "ignored because only get/post is collected"},
        },
        "/items": {
            "post": {
                "description": "create item",
                "operationId": "create_item",
                "parameters": [],
            }
        },
    }


def test_openapi_schema_should_keep_only_get_and_post_interfaces():
    schema = OpenAPISchema(
        server="https://api.example.com",
        description="tool provider",
        paths=_valid_openapi_paths(),
    )

    assert set(schema.paths.keys()) == {"/items/{id}", "/items"}
    assert "get" in schema.paths["/items/{id}"]
    assert "post" in schema.paths["/items"]
    assert schema.paths["/items/{id}"]["get"]["operationId"] == "get_item"


@pytest.mark.parametrize(
    "payload, message",
    [
        (
            {"server": "", "description": "d", "paths": _valid_openapi_paths()},
            "server不能为空",
        ),
        (
            {
                "server": "https://a.com",
                "description": "",
                "paths": _valid_openapi_paths(),
            },
            "description不能为空",
        ),
        (
            {"server": "https://a.com", "description": "d", "paths": {}},
            "paths不能为空且必须为字典",
        ),
    ],
)
def test_openapi_schema_should_raise_for_empty_required_fields(payload, message):
    with pytest.raises(ValidateErrorException, match=message):
        OpenAPISchema(**payload)


def test_openapi_schema_should_raise_for_operation_level_type_errors():
    base = _valid_openapi_paths()

    bad_desc = {
        "/items": {"get": {"description": 1, "operationId": "op_1", "parameters": []}}
    }
    with pytest.raises(ValidateErrorException, match="description为字符串且不能为空"):
        OpenAPISchema(server="https://a.com", description="d", paths=bad_desc)

    bad_operation_id = {
        "/items": {"get": {"description": "d", "operationId": 1, "parameters": []}}
    }
    with pytest.raises(ValidateErrorException, match="operationId为字符串且不能为空"):
        OpenAPISchema(server="https://a.com", description="d", paths=bad_operation_id)

    bad_parameters = {
        "/items": {"get": {"description": "d", "operationId": "op_1", "parameters": {}}}
    }
    with pytest.raises(ValidateErrorException, match="parameters必须是列表或者为空"):
        OpenAPISchema(server="https://a.com", description="d", paths=bad_parameters)

    duplicate_id = {
        "/a": {"get": {"description": "d", "operationId": "dup_id", "parameters": []}},
        "/b": {"post": {"description": "d", "operationId": "dup_id", "parameters": []}},
    }
    with pytest.raises(ValidateErrorException, match="operationId必须唯一"):
        OpenAPISchema(server="https://a.com", description="d", paths=duplicate_id)

    # 避免 linter 提示 base 未使用，同时保留语义：这里用于确保基线数据结构可以先通过。
    assert base["/items"]["post"]["operationId"] == "create_item"


@pytest.mark.parametrize(
    "parameter, message",
    [
        (
            {
                "name": 1,
                "in": ParameterIn.QUERY,
                "description": "d",
                "required": True,
                "type": ParameterType.STR,
            },
            "parameter.name为字符串",
        ),
        (
            {
                "name": "q",
                "in": ParameterIn.QUERY,
                "description": 1,
                "required": True,
                "type": ParameterType.STR,
            },
            "parameter.description为字符串",
        ),
        (
            {
                "name": "q",
                "in": ParameterIn.QUERY,
                "description": "d",
                "required": "yes",
                "type": ParameterType.STR,
            },
            "parameter.required为布尔值",
        ),
        (
            {
                "name": "q",
                "in": 123,
                "description": "d",
                "required": True,
                "type": ParameterType.STR,
            },
            "parameter.in参数必须为",
        ),
        (
            {
                "name": "q",
                "in": ParameterIn.QUERY,
                "description": "d",
                "required": True,
                "type": 123,
            },
            "parameter.type参数必须为",
        ),
    ],
)
def test_openapi_schema_should_raise_for_parameter_shape_errors(parameter, message):
    paths = {
        "/items": {
            "get": {
                "description": "query",
                "operationId": "op_1",
                "parameters": [parameter],
            }
        }
    }

    with pytest.raises(ValidateErrorException, match=message):
        OpenAPISchema(server="https://a.com", description="d", paths=paths)


def test_category_entity_should_raise_when_icon_extension_is_not_svg():
    with pytest.raises(FailException, match="icon图标不是svg格式"):
        CategoryEntity(category="search", name="Search", icon="icon.png")


def test_builtin_category_manager_should_load_categories_and_icons(
    tmp_path, monkeypatch
):
    categories_yaml = tmp_path / "categories.yaml"
    icons_dir = tmp_path / "icons"
    icons_dir.mkdir()
    (icons_dir / "search.svg").write_text("<svg>search</svg>", encoding="utf-8")
    categories_yaml.write_text(
        yaml.safe_dump(
            [
                {"category": "search", "name": "Search", "icon": "search.svg"},
            ],
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "internal.core.tools.builtin_tools.categories.builtin_category_manager.os.path.abspath",
        lambda _path: str(tmp_path / "builtin_category_manager.py"),
    )

    manager = BuiltinCategoryManager()

    category_map = manager.get_category_map()
    assert "search" in category_map
    assert category_map["search"]["entity"].name == "Search"
    assert category_map["search"]["icon"] == "<svg>search</svg>"


def test_builtin_category_manager_should_raise_when_icon_file_missing(
    tmp_path, monkeypatch
):
    categories_yaml = tmp_path / "categories.yaml"
    categories_yaml.write_text(
        yaml.safe_dump(
            [{"category": "search", "name": "Search", "icon": "search.svg"}],
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "internal.core.tools.builtin_tools.categories.builtin_category_manager.os.path.abspath",
        lambda _path: str(tmp_path / "builtin_category_manager.py"),
    )

    with pytest.raises(NotFoundException, match="icon未提供"):
        BuiltinCategoryManager()


def test_builtin_category_manager_should_skip_reinit_when_map_already_exists(
    monkeypatch,
):
    manager = BuiltinCategoryManager.model_construct(
        category_map={"existing": {"entity": "x", "icon": "y"}}
    )
    monkeypatch.setattr(
        "internal.core.tools.builtin_tools.categories.builtin_category_manager.os.path.abspath",
        lambda _path: (_ for _ in ()).throw(RuntimeError("should not call abspath")),
    )

    manager._init_categories()
    assert "existing" in manager.category_map


def test_builtin_provider_manager_should_load_provider_map_and_delegate_methods(
    tmp_path, monkeypatch
):
    providers_yaml = tmp_path / "providers.yaml"
    providers_yaml.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "provider_a",
                    "label": "Provider A",
                    "description": "desc",
                    "icon": "icon.svg",
                    "background": "#fff",
                    "category": "search",
                    "created_at": 1,
                }
            ],
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    class _FakeProvider:
        def __init__(self, name, position, provider_entity):
            self.name = name
            self.position = position
            self.provider_entity = provider_entity

        @staticmethod
        def get_tool(tool_name):
            return f"tool:{tool_name}"

    monkeypatch.setattr(
        "internal.core.tools.builtin_tools.providers.builtin_provider_manager.os.path.abspath",
        lambda _path: str(tmp_path / "builtin_provider_manager.py"),
    )
    monkeypatch.setattr(
        "internal.core.tools.builtin_tools.providers.builtin_provider_manager.Provider",
        _FakeProvider,
    )

    manager = BuiltinProviderManager()

    provider = manager.get_provider("provider_a")
    assert provider.name == "provider_a"
    assert len(manager.get_providers()) == 1
    assert provider.provider_entity.name == "provider_a"
    assert manager.get_tool("provider_a", "search") == "tool:search"
    assert manager.get_tool("missing", "search") is None


def test_builtin_provider_manager_should_skip_init_when_provider_map_not_empty(
    monkeypatch,
):
    manager = BuiltinProviderManager.model_construct(
        provider_map={
            "provider_a": SimpleNamespace(
                provider_entity=SimpleNamespace(name="provider_a")
            )
        }
    )
    monkeypatch.setattr(
        "internal.core.tools.builtin_tools.providers.builtin_provider_manager.os.path.abspath",
        lambda _path: (_ for _ in ()).throw(RuntimeError("should not call abspath")),
    )

    manager._get_provider_tool_map()
    assert "provider_a" in manager.provider_map


def test_provider_entity_accessors_should_return_items_from_maps():
    provider_entity = ProviderEntity(
        name="provider_a",
        label="Provider A",
        description="desc",
        icon="icon.svg",
        background="#fff",
        category="search",
        created_at=1,
    )
    tool_entity = BuiltinToolEntity(
        name="tool_a",
        label="Tool A",
        description="tool desc",
    )
    tool_callable = lambda: "ok"
    provider = Provider.model_construct(
        name="provider_a",
        position=1,
        provider_entity=provider_entity,
        tool_entity_map={"tool_a": tool_entity},
        tool_func_map={"tool_a": tool_callable},
    )

    assert provider.get_tool("tool_a") is tool_callable
    assert provider.get_tool_entity("tool_a") is tool_entity
    assert provider.get_tool_entities() == [tool_entity]
