import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
import requests

from internal.core.workflow.entities.node_entity import NodeResult
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType
from internal.core.workflow.nodes.code.code_entity import CodeNodeData
from internal.core.workflow.nodes.code.code_node import CodeNode
from internal.core.workflow.nodes.dataset_retrieval.dataset_retrieval_entity import DatasetRetrievalNodeData
from internal.core.workflow.nodes.dataset_retrieval.dataset_retrieval_node import DatasetRetrievalNode
from internal.core.workflow.nodes.end.end_entity import EndNodeData
from internal.core.workflow.nodes.end.end_node import EndNode
from internal.core.workflow.nodes.http_request.http_request_entity import (
    HttpRequestInputType,
    HttpRequestMethod,
    HttpRequestNodeData,
)
from internal.core.workflow.nodes.http_request.http_request_node import HttpRequestNode
from internal.core.workflow.nodes.llm.llm_entity import LLMNodeData
from internal.core.workflow.nodes.llm.llm_node import LLMNode
from internal.core.workflow.nodes.parameter_extractor.parameter_extractor_entity import (
    ParameterExtractorNodeData,
    ParameterExtractorMode,
)
from internal.core.workflow.nodes.parameter_extractor.parameter_extractor_node import (
    ParameterExtractorNode,
)
from internal.core.workflow.nodes.start.start_entity import StartNodeData
from internal.core.workflow.nodes.start.start_node import StartNode
from internal.core.workflow.nodes.template_transform.template_transform_entity import (
    TemplateTransformNodeData,
)
from internal.core.workflow.nodes.template_transform.template_transform_node import (
    TemplateTransformNode,
)
from internal.core.workflow.nodes.text_processor.text_processor_entity import (
    TextProcessorMode,
    TextProcessorNodeData,
)
from internal.core.workflow.nodes.text_processor.text_processor_node import TextProcessorNode
from internal.core.workflow.nodes.tool.tool_entity import ToolNodeData
from internal.core.workflow.nodes.tool.tool_node import ToolNode
from internal.core.workflow.nodes.variable_assigner.variable_assigner_entity import (
    VariableAssignerNodeData,
)
from internal.core.workflow.nodes.variable_assigner.variable_assigner_node import VariableAssignerNode
from internal.exception import FailException, NotFoundException


def _state_with_node_result(node_result):
    return {"inputs": {}, "outputs": {}, "node_results": [node_result]}


def _ref_var(name, ref_node_id, ref_var_name, var_type="string", meta=None):
    return VariableEntity(
        name=name,
        type=var_type,
        value={
            "type": VariableValueType.REF.value,
            "content": {"ref_node_id": ref_node_id, "ref_var_name": ref_var_name},
        },
        meta=meta or {},
    )


class TestStartEndTemplateNodes:
    def test_start_node_should_fill_optional_default_value_and_return_node_result(self):
        node_data = StartNodeData(
            id=uuid4(),
            node_type="start",
            title="start",
            inputs=[
                VariableEntity(name="query", type="string", required=True),
                VariableEntity(name="top_k", type="int", required=False),
            ],
        )
        node = StartNode(node_data=node_data)

        result = node.invoke({"inputs": {"query": "weather"}, "outputs": {}, "node_results": []})
        node_result = result["node_results"][0]

        assert node_result.outputs["query"] == "weather"
        assert node_result.outputs["top_k"] == 0
        assert node_result.status == "succeeded"

    def test_start_node_should_raise_when_required_input_missing(self):
        node_data = StartNodeData(
            id=uuid4(),
            node_type="start",
            title="start",
            inputs=[VariableEntity(name="query", type="string", required=True)],
        )
        node = StartNode(node_data=node_data)

        with pytest.raises(FailException, match="query为必填参数"):
            node.invoke({"inputs": {}, "outputs": {}, "node_results": []})

    def test_end_node_should_extract_ref_outputs_from_state(self):
        start_data = StartNodeData(id=uuid4(), node_type="start", title="start", inputs=[])
        previous_result = NodeResult(node_data=start_data, outputs={"answer": "done"})
        end_data = EndNodeData(
            id=uuid4(),
            node_type="end",
            title="end",
            outputs=[
                _ref_var(
                    name="final_answer",
                    ref_node_id=start_data.id,
                    ref_var_name="answer",
                )
            ],
        )
        node = EndNode(node_data=end_data)

        result = node.invoke(_state_with_node_result(previous_result))

        assert result["outputs"] == {"final_answer": "done"}
        assert result["node_results"][0].status == "succeeded"

    def test_template_transform_node_should_render_template_with_extracted_inputs(self):
        source_data = CodeNodeData(id=uuid4(), node_type="code", title="source", outputs=[])
        previous_result = NodeResult(node_data=source_data, outputs={"name": "Alice", "age": 18})
        node_data = TemplateTransformNodeData(
            id=uuid4(),
            node_type="template_transform",
            title="tpl",
            template="{{name}} is {{age}} years old",
            inputs=[
                _ref_var(name="name", ref_node_id=source_data.id, ref_var_name="name"),
                _ref_var(name="age", ref_node_id=source_data.id, ref_var_name="age", var_type="int"),
            ],
        )
        node = TemplateTransformNode(node_data=node_data)

        result = node.invoke(_state_with_node_result(previous_result))

        assert result["node_results"][0].outputs["output"] == "Alice is 18 years old"


class TestLLMAndDatasetNodes:
    def test_llm_node_should_stream_content_and_write_custom_output_key(self, monkeypatch):
        class _FakeLLM:
            @staticmethod
            def stream(_prompt):
                yield SimpleNamespace(content="hello ")
                yield SimpleNamespace(content="world")

        class _FakeLanguageModelService:
            @staticmethod
            def load_language_model(_cfg):
                return _FakeLLM()

        class _FakeInjector:
            @staticmethod
            def get(_service_cls):
                return _FakeLanguageModelService()

        monkeypatch.setattr("app.http.app.injector", _FakeInjector())

        source_data = CodeNodeData(id=uuid4(), node_type="code", title="source", outputs=[])
        previous_result = NodeResult(node_data=source_data, outputs={"query": "weather"})

        # 使用 model_construct 跳过 LLMNodeData 的 outputs 归一化规则，
        # 目的是覆盖 invoke 中“自定义输出字段名”的分支。
        node_data = LLMNodeData.model_construct(
            id=uuid4(),
            node_type="llm",
            title="llm",
            position={"x": 0, "y": 0},
            prompt="Answer {{query}}",
            language_model_config={},
            inputs=[_ref_var(name="query", ref_node_id=source_data.id, ref_var_name="query")],
            outputs=[VariableEntity(name="custom_text", value={"type": "generated"})],
        )
        node = LLMNode(node_data=node_data)

        result = node.invoke(_state_with_node_result(previous_result))

        assert result["node_results"][0].outputs["custom_text"] == "hello world"

    def test_llm_node_should_fallback_to_output_key_when_outputs_empty(self, monkeypatch):
        class _FakeLLM:
            @staticmethod
            def stream(_prompt):
                yield SimpleNamespace(content="ok")

        class _FakeLanguageModelService:
            @staticmethod
            def load_language_model(_cfg):
                return _FakeLLM()

        class _FakeInjector:
            @staticmethod
            def get(_service_cls):
                return _FakeLanguageModelService()

        monkeypatch.setattr("app.http.app.injector", _FakeInjector())

        source_data = CodeNodeData(id=uuid4(), node_type="code", title="source", outputs=[])
        previous_result = NodeResult(node_data=source_data, outputs={"query": "weather"})
        node_data = LLMNodeData.model_construct(
            id=uuid4(),
            node_type="llm",
            title="llm",
            position={"x": 0, "y": 0},
            prompt="Answer {{query}}",
            language_model_config={},
            inputs=[_ref_var(name="query", ref_node_id=source_data.id, ref_var_name="query")],
            outputs=[],
        )
        node = LLMNode(node_data=node_data)

        result = node.invoke(_state_with_node_result(previous_result))

        assert result["node_results"][0].outputs["output"] == "ok"

    def test_dataset_retrieval_node_should_init_and_invoke(self, monkeypatch, app):
        class _FakeRetrievalTool:
            @staticmethod
            def invoke(_payload):
                return "doc-1\ndoc-2"

        class _FakeRetrievalService:
            @staticmethod
            def create_langchain_tool_from_search(**kwargs):
                assert "dataset_ids" in kwargs
                return _FakeRetrievalTool()

        class _FakeInjector:
            @staticmethod
            def get(_cls):
                return _FakeRetrievalService()

        monkeypatch.setattr("app.http.module.injector", _FakeInjector())

        source_data = StartNodeData(id=uuid4(), node_type="start", title="start", inputs=[])
        previous_result = NodeResult(node_data=source_data, outputs={"query": "python"})
        node_data = DatasetRetrievalNodeData(
            id=uuid4(),
            node_type="dataset_retrieval",
            title="retrieval",
            dataset_ids=[uuid4()],
            inputs=[_ref_var(name="query", ref_node_id=source_data.id, ref_var_name="query")],
        )
        with app.app_context():
            node = DatasetRetrievalNode(
                flask_app=app,
                account_id=uuid4(),
                node_data=node_data,
            )
            result = node.invoke(_state_with_node_result(previous_result))

        assert result["node_results"][0].outputs["combine_documents"] == "doc-1\ndoc-2"

    def test_dataset_retrieval_node_should_fallback_output_key_when_outputs_empty(self, monkeypatch, app):
        payload_build_calls = []
        captured_kwargs = {}

        class _FakeRetrievalTool:
            @staticmethod
            def invoke(_payload):
                return "docs"

        class _FakeRetrievalService:
            @staticmethod
            def create_langchain_tool_from_search(**kwargs):
                captured_kwargs.update(kwargs)
                return _FakeRetrievalTool()

        class _FakeInjector:
            @staticmethod
            def get(_cls):
                return _FakeRetrievalService()

        monkeypatch.setattr("app.http.module.injector", _FakeInjector())

        source_data = StartNodeData(id=uuid4(), node_type="start", title="start", inputs=[])
        previous_result = NodeResult(node_data=source_data, outputs={"query": "python"})
        node_data = DatasetRetrievalNodeData.model_construct(
            id=uuid4(),
            node_type="dataset_retrieval",
            title="retrieval",
            position={"x": 0, "y": 0},
            dataset_ids=[uuid4()],
            retrieval_config=SimpleNamespace(
                # 兼容层校验：当前实现应优先使用 model_dump，而不是 legacy dict。
                model_dump=lambda: payload_build_calls.append("model_dump")
                or {"k": 4, "score": 0, "retrieval_strategy": "semantic"},
                dict=lambda: payload_build_calls.append("dict") or {"k": 1},
            ),
            inputs=[_ref_var(name="query", ref_node_id=source_data.id, ref_var_name="query")],
            outputs=[],
        )
        with app.app_context():
            node = DatasetRetrievalNode(
                flask_app=app,
                account_id=uuid4(),
                node_data=node_data,
            )
            result = node.invoke(_state_with_node_result(previous_result))

        assert result["node_results"][0].outputs["combine_documents"] == "docs"
        assert payload_build_calls == ["model_dump"]
        assert captured_kwargs["k"] == 4


class TestToolNode:
    def test_tool_node_should_raise_not_found_for_missing_builtin_tool(self, monkeypatch):
        class _BuiltinManager:
            @staticmethod
            def get_tool(_provider_id, _tool_id):
                return None

        class _Injector:
            @staticmethod
            def get(_cls):
                return _BuiltinManager()

        monkeypatch.setattr("app.http.module.injector", _Injector())
        node_data = ToolNodeData(
            id=uuid4(),
            node_type="tool",
            title="tool",
            type="builtin_tool",
            provider_id="provider_a",
            tool_id="tool_a",
            inputs=[],
            outputs=[],
        )

        with pytest.raises(NotFoundException, match="内置插件扩展不存在"):
            ToolNode(node_data=node_data)

    def test_tool_node_builtin_should_json_dump_non_string_result(self, monkeypatch):
        class _BuiltinTool:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            @staticmethod
            def invoke(_payload):
                return {"ok": True}

        class _BuiltinManager:
            @staticmethod
            def get_tool(_provider_id, _tool_id):
                return _BuiltinTool

        class _Injector:
            @staticmethod
            def get(_cls):
                return _BuiltinManager()

        monkeypatch.setattr("app.http.module.injector", _Injector())

        source_data = StartNodeData(id=uuid4(), node_type="start", title="start", inputs=[])
        previous_result = NodeResult(node_data=source_data, outputs={"query": "hello"})
        node_data = ToolNodeData(
            id=uuid4(),
            node_type="tool",
            title="tool",
            type="builtin_tool",
            provider_id="provider_a",
            tool_id="tool_a",
            params={"k": 3},
            inputs=[_ref_var(name="query", ref_node_id=source_data.id, ref_var_name="query")],
            outputs=[VariableEntity(name="tool_output", value={"type": "generated"})],
        )
        node = ToolNode(node_data=node_data)

        result = node.invoke(_state_with_node_result(previous_result))
        output_text = result["node_results"][0].outputs["tool_output"]

        assert json.loads(output_text)["ok"] is True

    def test_tool_node_should_raise_fail_exception_when_tool_invoke_failed(self, monkeypatch):
        class _BuiltinTool:
            def __init__(self, **kwargs):
                pass

            @staticmethod
            def invoke(_payload):
                raise RuntimeError("tool boom")

        class _BuiltinManager:
            @staticmethod
            def get_tool(_provider_id, _tool_id):
                return _BuiltinTool

        class _Injector:
            @staticmethod
            def get(_cls):
                return _BuiltinManager()

        monkeypatch.setattr("app.http.module.injector", _Injector())

        source_data = StartNodeData(id=uuid4(), node_type="start", title="start", inputs=[])
        previous_result = NodeResult(node_data=source_data, outputs={"query": "hello"})
        node_data = ToolNodeData(
            id=uuid4(),
            node_type="tool",
            title="tool",
            type="builtin_tool",
            provider_id="provider_a",
            tool_id="tool_a",
            inputs=[_ref_var(name="query", ref_node_id=source_data.id, ref_var_name="query")],
            outputs=[],
        )
        node = ToolNode(node_data=node_data)

        with pytest.raises(FailException, match="扩展插件执行失败"):
            node.invoke(_state_with_node_result(previous_result))

    def test_tool_node_api_branch_should_load_tool_from_db_and_invoke(self, monkeypatch):
        class _ApiProviderManager:
            @staticmethod
            def get_tool(_tool_entity):
                return SimpleNamespace(invoke=lambda _payload: "api-result")

        class _DbQuery:
            @staticmethod
            def filter(*_args):
                return _DbQuery()

            @staticmethod
            def one_or_none():
                return SimpleNamespace(
                    id=uuid4(),
                    name="api_tool",
                    url="https://example.com/tools/{tool_id}",
                    method="post",
                    description="tool-desc",
                    provider=SimpleNamespace(headers=[{"key": "x-api-key", "value": "abc"}]),
                    parameters=[{"name": "keyword", "type": "str", "in": "query", "required": True}],
                )

        class _DB:
            session = SimpleNamespace(query=lambda _model: _DbQuery())

        class _Injector:
            @staticmethod
            def get(cls):
                if cls.__name__ == "SQLAlchemy":
                    return _DB()
                return _ApiProviderManager()

        monkeypatch.setattr("app.http.module.injector", _Injector())

        source_data = StartNodeData(id=uuid4(), node_type="start", title="start", inputs=[])
        previous_result = NodeResult(node_data=source_data, outputs={"keyword": "python"})
        node_data = ToolNodeData(
            id=uuid4(),
            node_type="tool",
            title="tool",
            type="api_tool",
            provider_id="provider_a",
            tool_id="api_tool",
            inputs=[_ref_var(name="keyword", ref_node_id=source_data.id, ref_var_name="keyword")],
            outputs=[],
        )
        node = ToolNode(node_data=node_data)
        result = node.invoke(_state_with_node_result(previous_result))

        assert result["node_results"][0].outputs["text"] == "api-result"

    def test_tool_node_api_branch_should_raise_not_found_when_api_tool_missing(self, monkeypatch):
        class _DbQuery:
            @staticmethod
            def filter(*_args):
                return _DbQuery()

            @staticmethod
            def one_or_none():
                return None

        class _DB:
            session = SimpleNamespace(query=lambda _model: _DbQuery())

        class _Injector:
            @staticmethod
            def get(cls):
                if cls.__name__ == "SQLAlchemy":
                    return _DB()
                return SimpleNamespace()

        monkeypatch.setattr("app.http.module.injector", _Injector())

        node_data = ToolNodeData(
            id=uuid4(),
            node_type="tool",
            title="tool",
            type="api_tool",
            provider_id="provider_a",
            tool_id="api_tool",
            inputs=[],
            outputs=[],
        )

        with pytest.raises(NotFoundException, match="API扩展插件不存在"):
            ToolNode(node_data=node_data)

    def test_tool_node_should_fallback_text_output_when_outputs_is_empty(self, monkeypatch):
        class _BuiltinTool:
            def __init__(self, **kwargs):
                pass

            @staticmethod
            def invoke(_payload):
                return "plain-text"

        class _BuiltinManager:
            @staticmethod
            def get_tool(_provider_id, _tool_id):
                return _BuiltinTool

        class _Injector:
            @staticmethod
            def get(_cls):
                return _BuiltinManager()

        monkeypatch.setattr("app.http.module.injector", _Injector())

        source_data = StartNodeData(id=uuid4(), node_type="start", title="start", inputs=[])
        previous_result = NodeResult(node_data=source_data, outputs={"query": "hello"})
        node_data = ToolNodeData.model_construct(
            id=uuid4(),
            node_type="tool",
            title="tool",
            position={"x": 0, "y": 0},
            tool_type="builtin_tool",
            provider_id="provider_a",
            tool_id="tool_a",
            params={},
            inputs=[_ref_var(name="query", ref_node_id=source_data.id, ref_var_name="query")],
            outputs=[],
            meta={},
        )
        node = ToolNode(node_data=node_data)

        result = node.invoke(_state_with_node_result(previous_result))

        assert result["node_results"][0].outputs["text"] == "plain-text"


class TestHttpRequestNode:
    def test_http_request_node_should_send_get_request_with_params_and_headers(self, monkeypatch):
        captured = {}

        def _fake_get(url, headers, params):
            captured["url"] = url
            captured["headers"] = headers
            captured["params"] = params
            return SimpleNamespace(text="ok-get", status_code=200)

        monkeypatch.setattr("internal.core.workflow.nodes.http_request.http_request_node.requests.get", _fake_get)

        node_data = HttpRequestNodeData(
            id=uuid4(),
            node_type="http_request",
            title="http_get",
            url="https://api.example.com/v1/items",
            method=HttpRequestMethod.GET,
            inputs=[
                VariableEntity(
                    name="page",
                    type="int",
                    value={"type": "literal", "content": 1},
                    meta={"type": HttpRequestInputType.PARAMS},
                ),
                VariableEntity(
                    name="x_token",
                    type="string",
                    value={"type": "literal", "content": "token"},
                    meta={"type": HttpRequestInputType.HEADERS},
                ),
            ],
        )
        node = HttpRequestNode(node_data=node_data)

        result = node.invoke({"inputs": {}, "outputs": {}, "node_results": []})

        assert str(captured["url"]).startswith("https://api.example.com/v1/items")
        assert captured["params"] == {"page": 1}
        assert captured["headers"] == {"x_token": "token"}
        assert result["node_results"][0].outputs == {"text": "ok-get", "status_code": 200}

    def test_http_request_node_should_send_non_get_request_with_body(self, monkeypatch):
        captured = {}

        def _fake_post(url, headers, params, data):
            captured["url"] = url
            captured["headers"] = headers
            captured["params"] = params
            captured["data"] = data
            return SimpleNamespace(text="ok-post", status_code=201)

        monkeypatch.setattr("internal.core.workflow.nodes.http_request.http_request_node.requests.post", _fake_post)

        node_data = HttpRequestNodeData(
            id=uuid4(),
            node_type="http_request",
            title="http_post",
            url="https://api.example.com/v1/items",
            method=HttpRequestMethod.POST,
            inputs=[
                VariableEntity(
                    name="debug",
                    type="boolean",
                    value={"type": "literal", "content": True},
                    meta={"type": HttpRequestInputType.PARAMS},
                ),
                VariableEntity(
                    name="x_token",
                    type="string",
                    value={"type": "literal", "content": "token"},
                    meta={"type": HttpRequestInputType.HEADERS},
                ),
                VariableEntity(
                    name="payload",
                    type="string",
                    value={"type": "literal", "content": "hello"},
                    meta={"type": HttpRequestInputType.BODY},
                ),
            ],
        )
        node = HttpRequestNode(node_data=node_data)

        result = node.invoke({"inputs": {}, "outputs": {}, "node_results": []})

        assert captured["params"] == {"debug": True}
        assert captured["headers"] == {"x_token": "token"}
        assert captured["data"] == {"payload": "hello"}
        assert result["node_results"][0].outputs == {"text": "ok-post", "status_code": 201}


class TestTextProcessorNodes:
    @pytest.mark.parametrize(
        "mode, expected",
        [
            (TextProcessorMode.TRIM, "alice"),
            (TextProcessorMode.LOWER, "  alice  "),
            (TextProcessorMode.UPPER, "  ALICE  "),
            (TextProcessorMode.TITLE, "  Alice  "),
        ],
    )
    def test_text_processor_node_should_process_text_by_mode(self, mode, expected):
        node_data = TextProcessorNodeData(
            id=uuid4(),
            node_type="text_processor",
            title="text",
            mode=mode,
            inputs=[
                VariableEntity(
                    name="text",
                    type="string",
                    value={"type": "literal", "content": "  alice  "},
                )
            ],
        )
        node = TextProcessorNode(node_data=node_data)

        result = node.invoke({"inputs": {}, "outputs": {}, "node_results": []})
        outputs = result["node_results"][0].outputs

        assert outputs["output"] == expected
        assert outputs["length"] == len(expected)

    def test_text_processor_node_should_support_ref_input(self):
        source_data = StartNodeData(id=uuid4(), node_type="start", title="start", inputs=[])
        previous_result = NodeResult(node_data=source_data, outputs={"content": "  Hello  "})
        node_data = TextProcessorNodeData(
            id=uuid4(),
            node_type="text_processor",
            title="text",
            mode=TextProcessorMode.TRIM,
            inputs=[_ref_var(name="text", ref_node_id=source_data.id, ref_var_name="content")],
        )
        node = TextProcessorNode(node_data=node_data)

        result = node.invoke(_state_with_node_result(previous_result))

        assert result["node_results"][0].outputs["output"] == "Hello"


class TestVariableAssignerAndParameterExtractorNodes:
    def test_variable_assigner_node_should_assign_literal_and_ref_values(self):
        source_data = StartNodeData(id=uuid4(), node_type="start", title="start", inputs=[])
        previous_result = NodeResult(node_data=source_data, outputs={"name": "Alice"})
        node_data = VariableAssignerNodeData(
            id=uuid4(),
            node_type="variable_assigner",
            title="assigner",
            inputs=[
                _ref_var(name="name", ref_node_id=source_data.id, ref_var_name="name"),
                VariableEntity(name="score", type="int", value={"type": "literal", "content": 100}),
            ],
        )
        node = VariableAssignerNode(node_data=node_data)

        result = node.invoke(_state_with_node_result(previous_result))
        outputs = result["node_results"][0].outputs

        assert outputs["name"] == "Alice"
        assert outputs["score"] == 100

    def test_parameter_extractor_node_should_extract_from_json_and_cast_types(self):
        node_data = ParameterExtractorNodeData(
            id=uuid4(),
            node_type="parameter_extractor",
            title="extractor",
            mode=ParameterExtractorMode.JSON,
            inputs=[
                VariableEntity(
                    name="text",
                    type="string",
                    value={"type": "literal", "content": '{"name":"Alice","age":"20","active":"true"}'},
                )
            ],
            outputs=[
                VariableEntity(name="name", type="string", required=True),
                VariableEntity(name="age", type="int", required=True),
                VariableEntity(name="active", type="boolean", required=False),
            ],
        )
        node = ParameterExtractorNode(node_data=node_data)

        result = node.invoke({"inputs": {}, "outputs": {}, "node_results": []})
        outputs = result["node_results"][0].outputs

        assert outputs == {"name": "Alice", "age": 20, "active": True}

    def test_parameter_extractor_node_should_fallback_to_kv_in_auto_mode(self):
        node_data = ParameterExtractorNodeData(
            id=uuid4(),
            node_type="parameter_extractor",
            title="extractor",
            mode=ParameterExtractorMode.AUTO,
            inputs=[
                VariableEntity(
                    name="text",
                    type="string",
                    value={"type": "literal", "content": "city=Shanghai\ncount=3"},
                )
            ],
            outputs=[
                VariableEntity(name="city", type="string", required=True),
                VariableEntity(name="count", type="int", required=True),
            ],
        )
        node = ParameterExtractorNode(node_data=node_data)

        result = node.invoke({"inputs": {}, "outputs": {}, "node_results": []})

        assert result["node_results"][0].outputs == {"city": "Shanghai", "count": 3}

    def test_parameter_extractor_node_should_raise_for_invalid_json_in_json_mode(self):
        node_data = ParameterExtractorNodeData(
            id=uuid4(),
            node_type="parameter_extractor",
            title="extractor",
            mode=ParameterExtractorMode.JSON,
            inputs=[
                VariableEntity(
                    name="text",
                    type="string",
                    value={"type": "literal", "content": "name=Alice"},
                )
            ],
            outputs=[VariableEntity(name="name", type="string", required=True)],
        )
        node = ParameterExtractorNode(node_data=node_data)

        with pytest.raises(FailException, match="不是有效的JSON对象"):
            node.invoke({"inputs": {}, "outputs": {}, "node_results": []})

    def test_parameter_extractor_node_should_raise_when_required_field_missing(self):
        node_data = ParameterExtractorNodeData(
            id=uuid4(),
            node_type="parameter_extractor",
            title="extractor",
            mode=ParameterExtractorMode.KV,
            inputs=[
                VariableEntity(
                    name="text",
                    type="string",
                    value={"type": "literal", "content": "city=Shanghai"},
                )
            ],
            outputs=[VariableEntity(name="count", type="int", required=True)],
        )
        node = ParameterExtractorNode(node_data=node_data)

        with pytest.raises(FailException, match="缺少必填字段\\[count\\]"):
            node.invoke({"inputs": {}, "outputs": {}, "node_results": []})

    def test_parameter_extractor_node_should_use_default_for_optional_cast_failure(self):
        node_data = ParameterExtractorNodeData(
            id=uuid4(),
            node_type="parameter_extractor",
            title="extractor",
            mode=ParameterExtractorMode.KV,
            inputs=[
                VariableEntity(
                    name="text",
                    type="string",
                    value={"type": "literal", "content": "count=abc"},
                )
            ],
            outputs=[VariableEntity(name="count", type="int", required=False)],
        )
        node = ParameterExtractorNode(node_data=node_data)

        result = node.invoke({"inputs": {}, "outputs": {}, "node_results": []})

        assert result["node_results"][0].outputs["count"] == 0


class TestCodeNode:
    def test_code_node_invoke_should_map_outputs_and_fill_default(self, monkeypatch):
        node_data = CodeNodeData(
            id=uuid4(),
            node_type="code",
            title="code",
            inputs=[VariableEntity(name="name", type="string", value={"type": "literal", "content": "alice"})],
            outputs=[
                VariableEntity(name="greeting", type="string", value={"type": "generated"}),
                VariableEntity(name="score", type="int", value={"type": "generated"}),
            ],
        )
        node = CodeNode(node_data=node_data)
        monkeypatch.setattr(node, "_execute_function", lambda *_args, **_kwargs: {"greeting": "hi"})

        result = node.invoke({"inputs": {}, "outputs": {}, "node_results": []})

        outputs = result["node_results"][0].outputs
        assert outputs["greeting"] == "hi"
        assert outputs["score"] == 0

    def test_code_node_invoke_should_raise_when_result_is_not_dict(self, monkeypatch):
        node_data = CodeNodeData(
            id=uuid4(),
            node_type="code",
            title="code",
            outputs=[VariableEntity(name="greeting", type="string", value={"type": "generated"})],
        )
        node = CodeNode(node_data=node_data)
        monkeypatch.setattr(node, "_execute_function", lambda *_args, **_kwargs: "not-dict")

        with pytest.raises(FailException, match="返回值必须是一个字典"):
            node.invoke({"inputs": {}, "outputs": {}, "node_results": []})

    def test_execute_function_should_raise_when_sandbox_url_not_configured(self, monkeypatch):
        monkeypatch.setattr(CodeNode, "Sandbox_URL", "")
        with pytest.raises(FailException, match="SANDBOX_URL环境变量未配置"):
            CodeNode._execute_function("def main(params):\n    return params", params={})

    def test_execute_function_should_return_result_on_success(self, monkeypatch):
        monkeypatch.setattr(CodeNode, "Sandbox_URL", "https://sandbox.example.com")
        monkeypatch.setattr(
            "internal.core.workflow.nodes.code.code_node.requests.post",
            lambda *_args, **_kwargs: SimpleNamespace(status_code=200, json=lambda: {"result": {"x": 1}}),
        )

        result = CodeNode._execute_function("def main(params):\n    return params", params={"x": 1})

        assert result == {"x": 1}

    def test_execute_function_should_support_positional_args_path(self, monkeypatch):
        captured = {}

        def _fake_post(_url, *args, **kwargs):
            captured["payload"] = json.loads(kwargs["data"])
            return SimpleNamespace(status_code=200, json=lambda: {"result": {"ok": True}})

        monkeypatch.setattr(CodeNode, "Sandbox_URL", "https://sandbox.example.com")
        monkeypatch.setattr("internal.core.workflow.nodes.code.code_node.requests.post", _fake_post)

        result = CodeNode._execute_function("def main(a, b):\n    return {'sum': a + b}", 1, 2)

        assert result == {"ok": True}
        assert captured["payload"]["args"] == [1, 2]

    def test_execute_function_should_support_empty_args_and_kwargs_path(self, monkeypatch):
        captured = {}

        def _fake_post(_url, *args, **kwargs):
            captured["payload"] = json.loads(kwargs["data"])
            return SimpleNamespace(status_code=200, json=lambda: {"result": {"ok": True}})

        monkeypatch.setattr(CodeNode, "Sandbox_URL", "https://sandbox.example.com")
        monkeypatch.setattr("internal.core.workflow.nodes.code.code_node.requests.post", _fake_post)

        result = CodeNode._execute_function("def main():\n    return {'ok': True}")

        assert result == {"ok": True}
        assert captured["payload"]["args"] == []
        assert captured["payload"]["kwargs"] == {}

    def test_execute_function_should_raise_on_http_error(self, monkeypatch):
        monkeypatch.setattr(CodeNode, "Sandbox_URL", "https://sandbox.example.com")
        monkeypatch.setattr(
            "internal.core.workflow.nodes.code.code_node.requests.post",
            lambda *_args, **_kwargs: SimpleNamespace(
                status_code=500,
                json=lambda: {"msg": "boom"},
                text="boom",
            ),
        )

        with pytest.raises(FailException, match="云函数执行失败"):
            CodeNode._execute_function("def main(params):\n    return params", params={})

    def test_execute_function_should_fallback_raw_text_when_http_error_body_not_json(self, monkeypatch):
        monkeypatch.setattr(CodeNode, "Sandbox_URL", "https://sandbox.example.com")
        monkeypatch.setattr(
            "internal.core.workflow.nodes.code.code_node.requests.post",
            lambda *_args, **_kwargs: SimpleNamespace(
                status_code=502,
                json=lambda: (_ for _ in ()).throw(ValueError("bad json")),
                text="gateway error",
            ),
        )

        with pytest.raises(FailException, match="gateway error"):
            CodeNode._execute_function("def main(params):\n    return params", params={})

    def test_execute_function_should_raise_when_response_is_not_json(self, monkeypatch):
        monkeypatch.setattr(CodeNode, "Sandbox_URL", "https://sandbox.example.com")
        monkeypatch.setattr(
            "internal.core.workflow.nodes.code.code_node.requests.post",
            lambda *_args, **_kwargs: SimpleNamespace(
                status_code=200,
                json=lambda: (_ for _ in ()).throw(ValueError("not json")),
                text="<html>oops</html>",
            ),
        )

        with pytest.raises(FailException, match="云函数返回非JSON内容"):
            CodeNode._execute_function("def main(params):\n    return params", params={})

    @pytest.mark.parametrize(
        "payload, message",
        [
            ({"error": "runtime boom", "traceback": "tb-line"}, "代码执行出错: runtime boom"),
            ({"error": "runtime boom"}, "代码执行出错: runtime boom"),
            ({"unexpected": "field"}, "云函数返回数据格式错误"),
        ],
    )
    def test_execute_function_should_raise_on_invalid_result_payload(self, monkeypatch, payload, message):
        monkeypatch.setattr(CodeNode, "Sandbox_URL", "https://sandbox.example.com")
        monkeypatch.setattr(
            "internal.core.workflow.nodes.code.code_node.requests.post",
            lambda *_args, **_kwargs: SimpleNamespace(status_code=200, json=lambda: payload),
        )

        with pytest.raises(FailException, match=message):
            CodeNode._execute_function("def main(params):\n    return params", params={})

    @pytest.mark.parametrize(
        "error, message",
        [
            (requests.exceptions.Timeout(), "云函数执行超时"),
            (requests.exceptions.RequestException("net boom"), "网络请求失败"),
            (RuntimeError("unknown boom"), "Python代码执行出错"),
        ],
    )
    def test_execute_function_should_map_requests_and_generic_errors(self, monkeypatch, error, message):
        monkeypatch.setattr(CodeNode, "Sandbox_URL", "https://sandbox.example.com")
        monkeypatch.setattr(
            "internal.core.workflow.nodes.code.code_node.requests.post",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        )

        with pytest.raises(FailException, match=message):
            CodeNode._execute_function("def main(params):\n    return params", params={})
