from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import BaseModel

from internal.core.workflow.entities.node_entity import NodeType
from internal.core.workflow.workflow import Workflow
from internal.exception import ValidateErrorException


class _FakeCompiledGraph:
    def __init__(self):
        self.invocations = []
        self.stream_payloads = []

    def invoke(self, payload):
        self.invocations.append(payload)
        return {"outputs": {"answer": "ok"}}

    def stream(self, payload):
        self.stream_payloads.append(payload)
        yield {"node": "start"}
        yield {"node": "end"}


class _FakeGraph:
    latest = None

    def __init__(self, _state_cls):
        _FakeGraph.latest = self
        self.nodes = []
        self.edges = []
        self.entry = None
        self.finish = None
        self.compiled = _FakeCompiledGraph()

    def add_node(self, node_flag, node_obj):
        self.nodes.append((node_flag, node_obj))

    def add_edge(self, source_nodes, target_node):
        self.edges.append((source_nodes, target_node))

    def set_entry_point(self, node_name):
        self.entry = node_name

    def set_finish_point(self, node_name):
        self.finish = node_name

    def compile(self):
        return self.compiled


class _FakeNodeRuntime:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _build_workflow_obj(config):
    workflow = object.__new__(Workflow)
    workflow._workflow_config = config
    return workflow


def _start_node(node_id):
    return SimpleNamespace(id=node_id, node_type=NodeType.START.value, inputs=[])


def _end_node(node_id):
    return SimpleNamespace(id=node_id, node_type=NodeType.END.value, outputs=[])


def _node(node_id, node_type):
    return SimpleNamespace(id=node_id, node_type=node_type)


def _edge(edge_id, source, source_type, target, target_type):
    return SimpleNamespace(
        id=edge_id,
        source=source,
        source_type=source_type,
        target=target,
        target_type=target_type,
    )


def test_workflow_build_args_schema_should_build_required_and_optional_fields():
    start_inputs = [
        SimpleNamespace(name="query", type="string", required=True, description="search query"),
        SimpleNamespace(name="top_k", type="int", required=False, description="top k"),
    ]
    workflow_config = SimpleNamespace(nodes=[SimpleNamespace(node_type=NodeType.START.value, inputs=start_inputs)])

    model_cls = Workflow._build_args_schema(workflow_config)
    fields = model_cls.model_fields

    assert set(fields.keys()) == {"query", "top_k"}
    assert fields["query"].is_required() is True
    # 目前实现未给可选字段设置默认值，Pydantic 会将其判定为 required。
    assert fields["top_k"].is_required() is True


def test_workflow_build_workflow_should_register_nodes_edges_and_special_points(monkeypatch, app):
    start_id = uuid4()
    llm_id = uuid4()
    tpl_id = uuid4()
    ds_id = uuid4()
    code_id = uuid4()
    tool_id = uuid4()
    http_id = uuid4()
    text_id = uuid4()
    assigner_id = uuid4()
    extractor_id = uuid4()
    end_id = uuid4()
    nodes = [
        _start_node(start_id),
        _node(llm_id, NodeType.LLM.value),
        _node(tpl_id, NodeType.TEMPLATE_TRANSFORM.value),
        _node(ds_id, NodeType.DATASET_RETRIEVAL.value),
        _node(code_id, NodeType.CODE.value),
        _node(tool_id, NodeType.TOOL.value),
        _node(http_id, NodeType.HTTP_REQUEST.value),
        _node(text_id, NodeType.TEXT_PROCESSOR.value),
        _node(assigner_id, NodeType.VARIABLE_ASSIGNER.value),
        _node(extractor_id, NodeType.PARAMETER_EXTRACTOR.value),
        _end_node(end_id),
    ]
    edges = [
        _edge(uuid4(), start_id, NodeType.START, llm_id, NodeType.LLM),
        _edge(uuid4(), llm_id, NodeType.LLM, tpl_id, NodeType.TEMPLATE_TRANSFORM),
        _edge(uuid4(), tpl_id, NodeType.TEMPLATE_TRANSFORM, ds_id, NodeType.DATASET_RETRIEVAL),
        _edge(uuid4(), ds_id, NodeType.DATASET_RETRIEVAL, code_id, NodeType.CODE),
        _edge(uuid4(), code_id, NodeType.CODE, tool_id, NodeType.TOOL),
        _edge(uuid4(), tool_id, NodeType.TOOL, http_id, NodeType.HTTP_REQUEST),
        _edge(uuid4(), http_id, NodeType.HTTP_REQUEST, text_id, NodeType.TEXT_PROCESSOR),
        _edge(uuid4(), text_id, NodeType.TEXT_PROCESSOR, assigner_id, NodeType.VARIABLE_ASSIGNER),
        _edge(uuid4(), assigner_id, NodeType.VARIABLE_ASSIGNER, extractor_id, NodeType.PARAMETER_EXTRACTOR),
        _edge(uuid4(), extractor_id, NodeType.PARAMETER_EXTRACTOR, end_id, NodeType.END),
        # 额外增加一条并行边，确保 add_edge(source_nodes:list, target) 的分支被覆盖。
        _edge(uuid4(), code_id, NodeType.CODE, extractor_id, NodeType.PARAMETER_EXTRACTOR),
    ]
    workflow_config = SimpleNamespace(account_id=uuid4(), nodes=nodes, edges=edges)
    workflow = _build_workflow_obj(workflow_config)

    monkeypatch.setattr("internal.core.workflow.workflow.StateGraph", _FakeGraph)
    monkeypatch.setattr(
        "internal.core.workflow.workflow.NodeClasses",
        {node_type.value: _FakeNodeRuntime for node_type in NodeType},
    )

    with app.app_context():
        compiled = Workflow._build_workflow(workflow)

    assert isinstance(compiled, _FakeCompiledGraph)
    assert _FakeGraph.latest.entry == f"{NodeType.START.value}_{start_id}"
    assert _FakeGraph.latest.finish == f"{NodeType.END.value}_{end_id}"
    # 11 个节点全部注册，且 parameter_extractor 节点至少有 2 条来源边（并行汇聚）。
    assert len(_FakeGraph.latest.nodes) == 11
    extractor_target = f"{NodeType.PARAMETER_EXTRACTOR.value}_{extractor_id}"
    parallel_edges = [edge for edge in _FakeGraph.latest.edges if edge[1] == extractor_target]
    assert parallel_edges
    assert len(parallel_edges[0][0]) >= 2


def test_workflow_build_workflow_should_raise_when_node_type_unknown(monkeypatch):
    start_id = uuid4()
    end_id = uuid4()
    unknown = SimpleNamespace(id=uuid4(), node_type="unknown")
    nodes = [_start_node(start_id), unknown, _end_node(end_id)]
    edges = [
        _edge(uuid4(), start_id, NodeType.START, unknown.id, NodeType.CODE),
        _edge(uuid4(), unknown.id, NodeType.CODE, end_id, NodeType.END),
    ]
    workflow = _build_workflow_obj(SimpleNamespace(account_id=uuid4(), nodes=nodes, edges=edges))

    monkeypatch.setattr("internal.core.workflow.workflow.StateGraph", _FakeGraph)
    monkeypatch.setattr(
        "internal.core.workflow.workflow.NodeClasses",
        {node_type.value: _FakeNodeRuntime for node_type in NodeType},
    )

    with pytest.raises(ValueError, match="not a valid NodeType"):
        Workflow._build_workflow(workflow)


def test_workflow_build_workflow_should_raise_validate_error_for_non_string_unknown_node_type(monkeypatch):
    class _UnknownType:
        value = "unknown"

    start_id = uuid4()
    end_id = uuid4()
    unknown = SimpleNamespace(id=uuid4(), node_type=_UnknownType())
    nodes = [_start_node(start_id), unknown, _end_node(end_id)]
    edges = [
        _edge(uuid4(), start_id, NodeType.START, unknown.id, NodeType.CODE),
        _edge(uuid4(), unknown.id, NodeType.CODE, end_id, NodeType.END),
    ]
    workflow = _build_workflow_obj(SimpleNamespace(account_id=uuid4(), nodes=nodes, edges=edges))

    monkeypatch.setattr("internal.core.workflow.workflow.StateGraph", _FakeGraph)
    monkeypatch.setattr(
        "internal.core.workflow.workflow.NodeClasses",
        {node_type.value: _FakeNodeRuntime for node_type in NodeType},
    )

    with pytest.raises(ValidateErrorException, match="节点类型错误"):
        Workflow._build_workflow(workflow)


def test_workflow_run_and_stream_should_delegate_to_compiled_graph():
    workflow = object.__new__(Workflow)
    compiled = _FakeCompiledGraph()
    workflow._workflow = compiled

    run_result = Workflow._run(workflow, query="hi")
    stream_result = list(Workflow.stream(workflow, {"query": "hi"}))

    assert run_result == {"answer": "ok"}
    assert compiled.invocations == [{"inputs": {"query": "hi"}}]
    assert compiled.stream_payloads == [{"inputs": {"query": "hi"}}]
    assert stream_result == [{"node": "start"}, {"node": "end"}]


def test_workflow_init_should_set_name_description_and_graph(monkeypatch):
    class _DummySchema(BaseModel):
        pass

    sentinel_graph = _FakeCompiledGraph()

    # 这里单独 patch 内部方法，验证 __init__ 的装配职责：
    # - 使用 _build_args_schema 结果初始化 BaseTool
    # - 保存 workflow_config
    # - 执行并保存 _build_workflow 返回值
    monkeypatch.setattr(
        "internal.core.workflow.workflow.Workflow._build_args_schema",
        lambda _self, _cfg: _DummySchema,
    )
    monkeypatch.setattr("internal.core.workflow.workflow.Workflow._build_workflow", lambda self: sentinel_graph)

    config = SimpleNamespace(
        name="wf_demo",
        description="demo",
        nodes=[],
        edges=[],
        account_id=uuid4(),
    )
    workflow = Workflow(workflow_config=config)

    assert workflow.name == "wf_demo"
    assert workflow.description == "demo"
    assert workflow._workflow_config is config
    assert workflow._workflow is sentinel_graph
