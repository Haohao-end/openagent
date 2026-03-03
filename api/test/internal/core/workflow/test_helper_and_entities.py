from collections import defaultdict
from types import SimpleNamespace
from uuid import uuid4

import pytest

from internal.core.workflow.entities.node_entity import NodeResult
from internal.core.workflow.entities.node_entity import NodeType, BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType
from internal.core.workflow.entities.workflow_entity import (
    WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH,
    WorkflowConfig,
    _process_dict,
    _process_node_results,
)
from internal.core.workflow.nodes.code.code_entity import CodeNodeData
from internal.core.workflow.nodes.start.start_entity import StartNodeData
from internal.core.workflow.utils.helper import extract_variables_from_state
from internal.exception import ValidateErrorException


def _start_node(node_id, title="start", inputs=None):
    return {
        "id": node_id,
        "node_type": "start",
        "title": title,
        "description": "",
        "position": {"x": 0, "y": 0},
        "inputs": inputs
        if inputs is not None
        else [
            {
                "name": "query",
                "description": "query",
                "required": True,
                "type": "string",
                "value": {"type": VariableValueType.GENERATED.value, "content": ""},
            }
        ],
    }


def _end_node(node_id, title="end", outputs=None):
    return {
        "id": node_id,
        "node_type": "end",
        "title": title,
        "description": "",
        "position": {"x": 100, "y": 0},
        "outputs": outputs if outputs is not None else [],
    }


def _code_node(node_id, title):
    return {
        "id": node_id,
        "node_type": "code",
        "title": title,
        "description": "",
        "position": {"x": 50, "y": 0},
        "code": "def main(params):\n    return params",
        "inputs": [],
        "outputs": [],
    }


def _edge(edge_id, source, source_type, target, target_type):
    return {
        "id": edge_id,
        "source": source,
        "source_type": source_type,
        "target": target,
        "target_type": target_type,
    }


def _build_valid_payload():
    start_id = uuid4()
    end_id = uuid4()
    payload = {
        "account_id": uuid4(),
        "name": "wf_valid_1",
        "description": "workflow description",
        "nodes": [
            _start_node(start_id),
            _end_node(
                end_id,
                outputs=[
                    {
                        "name": "answer",
                        "description": "",
                        "required": True,
                        "type": "string",
                        "value": {
                            "type": VariableValueType.REF.value,
                            "content": {"ref_node_id": str(start_id), "ref_var_name": "query"},
                        },
                    }
                ],
            ),
        ],
        "edges": [_edge(uuid4(), start_id, "start", end_id, "end")],
    }
    return payload


def test_process_helpers_should_merge_dict_and_node_results():
    start_data = StartNodeData(id=uuid4(), node_type="start", title="s", inputs=[])
    result = NodeResult(node_data=start_data, outputs={"x": "1"})

    assert _process_dict(None, {"a": 1}) == {"a": 1}
    assert _process_dict({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
    assert _process_node_results(None, [result]) == [result]
    assert _process_node_results([result], []) == [result]


def test_extract_variables_from_state_should_handle_literal_ref_and_default_value():
    source_node = CodeNodeData(id=uuid4(), node_type="code", title="source", outputs=[])
    state = {
        "inputs": {},
        "outputs": {},
        "node_results": [
            NodeResult(
                node_data=source_node,
                outputs={"name": "alice", "active": True},
            )
        ],
    }
    variables = [
        VariableEntity(name="count", type="int", value={"type": "literal", "content": "3"}),
        VariableEntity(
            name="nickname",
            type="string",
            value={
                "type": "ref",
                "content": {"ref_node_id": source_node.id, "ref_var_name": "name"},
            },
        ),
        VariableEntity(
            name="missing_bool",
            type="boolean",
            value={
                "type": "ref",
                "content": {"ref_node_id": source_node.id, "ref_var_name": "not_exist"},
            },
        ),
    ]

    result = extract_variables_from_state(variables, state)

    assert result["count"] == 3
    assert result["nickname"] == "alice"
    assert result["missing_bool"] is False


def test_extract_variables_from_state_should_scan_all_node_results_until_reference_matches():
    # 构造两个节点结果：第一个不匹配，第二个匹配。
    # 该用例用于覆盖 helper 中 `if ... == ref_node_id` 的 false->继续循环分支。
    first_node = CodeNodeData(id=uuid4(), node_type="code", title="first", outputs=[])
    target_node = CodeNodeData(id=uuid4(), node_type="code", title="target", outputs=[])
    state = {
        "inputs": {},
        "outputs": {},
        "node_results": [
            NodeResult(node_data=first_node, outputs={"name": "first"}),
            NodeResult(node_data=target_node, outputs={"name": "target"}),
        ],
    }
    variables = [
        VariableEntity(
            name="picked_name",
            type="string",
            value={
                "type": "ref",
                "content": {"ref_node_id": target_node.id, "ref_var_name": "name"},
            },
        ),
    ]

    result = extract_variables_from_state(variables, state)

    assert result["picked_name"] == "target"


def test_extract_variables_from_state_should_return_default_when_node_not_executed():
    # 测试条件分支场景：当引用的节点未被执行时（不在 node_results 中），应返回默认值
    executed_node = CodeNodeData(id=uuid4(), node_type="code", title="executed", outputs=[])
    unexecuted_node_id = uuid4()  # 这个节点未执行，不在 node_results 中

    state = {
        "inputs": {},
        "outputs": {},
        "node_results": [
            NodeResult(node_data=executed_node, outputs={"result": "success"}),
        ],
    }

    variables = [
        # 引用已执行节点的变量 - 应该正常获取
        VariableEntity(
            name="executed_result",
            type="string",
            value={
                "type": "ref",
                "content": {"ref_node_id": executed_node.id, "ref_var_name": "result"},
            },
        ),
        # 引用未执行节点的字符串变量 - 应返回空字符串
        VariableEntity(
            name="unexecuted_string",
            type="string",
            value={
                "type": "ref",
                "content": {"ref_node_id": unexecuted_node_id, "ref_var_name": "some_var"},
            },
        ),
        # 引用未执行节点的整数变量 - 应返回 0
        VariableEntity(
            name="unexecuted_int",
            type="int",
            value={
                "type": "ref",
                "content": {"ref_node_id": unexecuted_node_id, "ref_var_name": "count"},
            },
        ),
        # 引用未执行节点的布尔变量 - 应返回 False
        VariableEntity(
            name="unexecuted_bool",
            type="boolean",
            value={
                "type": "ref",
                "content": {"ref_node_id": unexecuted_node_id, "ref_var_name": "flag"},
            },
        ),
    ]

    result = extract_variables_from_state(variables, state)

    assert result["executed_result"] == "success"
    assert result["unexecuted_string"] == ""
    assert result["unexecuted_int"] == 0
    assert result["unexecuted_bool"] is False


def test_workflow_config_should_validate_for_minimal_valid_graph():
    payload = _build_valid_payload()

    config = WorkflowConfig(**payload)

    assert config.name == "wf_valid_1"
    assert len(config.nodes) == 2
    assert len(config.edges) == 1


@pytest.mark.parametrize(
    "mutator, error_message",
    [
        (lambda p: p.update({"name": "1bad_name"}), "工作流名字仅支持"),
        (lambda p: p.update({"description": ""}), "工作流描述信息长度不能超过1024个字符"),
        (
            lambda p: p.update({"description": "x" * (WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH + 1)}),
            "工作流描述信息长度不能超过1024个字符",
        ),
        (lambda p: p.update({"nodes": "oops"}), "工作流节点列表信息错误"),
        (lambda p: p.update({"edges": "oops"}), "工作流边列表信息错误"),
    ],
)
def test_workflow_config_should_raise_on_basic_invalid_fields(mutator, error_message):
    payload = _build_valid_payload()
    mutator(payload)

    with pytest.raises(ValidateErrorException, match=error_message):
        WorkflowConfig(**payload)


def test_workflow_config_should_raise_when_node_or_edge_item_not_dict():
    payload = _build_valid_payload()
    payload["nodes"] = ["bad_node"]
    with pytest.raises(ValidateErrorException, match="工作流节点数据类型出错"):
        WorkflowConfig(**payload)

    payload = _build_valid_payload()
    payload["edges"] = ["bad_edge"]
    with pytest.raises(ValidateErrorException, match="工作流边数据类型出错"):
        WorkflowConfig(**payload)


def test_workflow_config_should_raise_on_node_uniqueness_and_type_errors():
    payload = _build_valid_payload()
    payload["nodes"][0]["node_type"] = "bad_type"
    with pytest.raises(ValidateErrorException, match="工作流节点类型出错"):
        WorkflowConfig(**payload)

    payload = _build_valid_payload()
    duplicate_start = _start_node(uuid4(), title="start_2")
    payload["nodes"].insert(1, duplicate_start)
    payload["edges"] = [
        payload["edges"][0],
        _edge(uuid4(), duplicate_start["id"], "start", payload["nodes"][1]["id"], "end"),
    ]
    with pytest.raises(ValidateErrorException, match="只允许有1个开始节点"):
        WorkflowConfig(**payload)

    payload = _build_valid_payload()
    duplicate_end = _end_node(uuid4(), title="end_2")
    payload["nodes"].append(duplicate_end)
    payload["edges"].append(
        _edge(uuid4(), payload["nodes"][0]["id"], "start", duplicate_end["id"], "end")
    )
    with pytest.raises(ValidateErrorException, match="只允许有1个结束节点"):
        WorkflowConfig(**payload)

    payload = _build_valid_payload()
    start_id = payload["nodes"][0]["id"]
    end_id = payload["nodes"][1]["id"]
    # 详细说明：在不改变节点类型的前提下复制一条边，可以精准命中 source+target 唯一性校验分支。
    payload["edges"] = [
        _edge(uuid4(), start_id, "start", end_id, "end"),
        _edge(uuid4(), start_id, "start", end_id, "end"),
    ]
    with pytest.raises(ValidateErrorException, match="工作流边数据不能重复添加"):
        WorkflowConfig(**payload)


def test_workflow_config_should_raise_when_node_id_or_title_duplicated():
    payload = _build_valid_payload()
    start_id = payload["nodes"][0]["id"]
    payload["nodes"][1]["id"] = start_id
    with pytest.raises(ValidateErrorException, match="节点id必须唯一"):
        WorkflowConfig(**payload)

    payload = _build_valid_payload()
    payload["nodes"][1]["title"] = payload["nodes"][0]["title"]
    with pytest.raises(ValidateErrorException, match="节点title必须唯一"):
        WorkflowConfig(**payload)


def test_workflow_config_should_raise_when_edge_source_target_mismatch_or_duplicate_id():
    payload = _build_valid_payload()
    payload["edges"][0]["source_type"] = "llm"
    with pytest.raises(ValidateErrorException, match="边起点/终点对应的节点不存在或类型错误"):
        WorkflowConfig(**payload)

    payload = _build_valid_payload()
    payload["edges"].append(dict(payload["edges"][0]))
    with pytest.raises(ValidateErrorException, match="工作流边数据id必须唯一"):
        WorkflowConfig(**payload)


def test_workflow_config_should_raise_when_graph_not_connected():
    start_id = uuid4()
    code_1 = uuid4()
    end_id = uuid4()
    code_2 = uuid4()
    code_3 = uuid4()
    payload = {
        "account_id": uuid4(),
        "name": "wf_not_connected",
        "description": "desc",
        "nodes": [
            _start_node(start_id),
            _code_node(code_1, "code_1"),
            _end_node(end_id),
            _code_node(code_2, "code_2"),
            _code_node(code_3, "code_3"),
        ],
        "edges": [
            _edge(uuid4(), start_id, "start", code_1, "code"),
            _edge(uuid4(), code_1, "code", end_id, "end"),
            _edge(uuid4(), code_2, "code", code_3, "code"),
            _edge(uuid4(), code_3, "code", code_2, "code"),
        ],
    }

    with pytest.raises(ValidateErrorException, match="图不联通"):
        WorkflowConfig(**payload)


def test_workflow_config_should_raise_when_graph_has_cycle():
    start_id = uuid4()
    code_1 = uuid4()
    code_2 = uuid4()
    end_id = uuid4()
    payload = {
        "account_id": uuid4(),
        "name": "wf_cycle",
        "description": "desc",
        "nodes": [
            _start_node(start_id),
            _code_node(code_1, "code_1"),
            _code_node(code_2, "code_2"),
            _end_node(end_id),
        ],
        "edges": [
            _edge(uuid4(), start_id, "start", code_1, "code"),
            _edge(uuid4(), code_1, "code", code_2, "code"),
            _edge(uuid4(), code_2, "code", code_1, "code"),
            _edge(uuid4(), code_2, "code", end_id, "end"),
        ],
    }

    with pytest.raises(ValidateErrorException, match="存在环路"):
        WorkflowConfig(**payload)


def test_workflow_config_should_raise_when_start_or_end_not_unique_by_degrees():
    start_id = uuid4()
    end_id = uuid4()
    code_a = uuid4()
    code_b = uuid4()
    payload = {
        "account_id": uuid4(),
        "name": "wf_multi_start_end",
        "description": "desc",
        "nodes": [
            _start_node(start_id),
            _code_node(code_a, "code_a"),
            _code_node(code_b, "code_b"),
            _end_node(end_id),
        ],
        "edges": [
            _edge(uuid4(), start_id, "start", code_a, "code"),
            # code_b 不作为任意节点的 target，形成第二个入度为 0 的起点分支。
            _edge(uuid4(), code_b, "code", end_id, "end"),
            _edge(uuid4(), code_a, "code", end_id, "end"),
        ],
    }

    with pytest.raises(ValidateErrorException, match="有且只有一个开始/结束节点"):
        WorkflowConfig(**payload)


def test_workflow_config_should_raise_when_ref_node_is_not_predecessor():
    payload = _build_valid_payload()
    payload["nodes"][1]["outputs"][0]["value"]["content"]["ref_node_id"] = str(uuid4())

    with pytest.raises(ValidateErrorException, match="引用数据出错"):
        WorkflowConfig(**payload)


def test_workflow_config_should_raise_when_ref_var_name_not_exists():
    payload = _build_valid_payload()
    payload["nodes"][1]["outputs"][0]["value"]["content"]["ref_var_name"] = "missing_var"

    with pytest.raises(ValidateErrorException, match="引用了不存在的节点变量"):
        WorkflowConfig(**payload)


def test_workflow_config_should_accept_literal_variable_refs_and_node_type_enum_value():
    start_id = uuid4()
    end_id = uuid4()
    payload = {
        "account_id": uuid4(),
        "name": "wf_literal_ref",
        "description": "desc",
        "nodes": [
            _start_node(start_id),
            _end_node(
                end_id,
                outputs=[
                    {
                        "name": "answer",
                        "description": "",
                        "required": True,
                        "type": "string",
                        # 非 ref 类型，覆盖 _validate_inputs_ref 的 false 分支。
                        "value": {"type": VariableValueType.LITERAL.value, "content": "ok"},
                    }
                ],
            ),
        ],
        "edges": [_edge(uuid4(), start_id, "start", end_id, "end")],
    }
    config = WorkflowConfig(**payload)
    assert config.nodes[1].outputs[0].value.type == VariableValueType.LITERAL.value

    # 覆盖 node_type 已是 Enum 的转换分支。
    node = BaseNodeData(id=uuid4(), node_type=NodeType.START, title="start")
    assert node.node_type == NodeType.START


def test_workflow_config_static_graph_helpers_should_work_with_cycles():
    a = uuid4()
    b = uuid4()
    c = uuid4()
    reverse_adj = defaultdict(list, {b: [a], c: [b], a: [c]})

    predecessors = WorkflowConfig._get_predecessors(reverse_adj, c)

    assert set(predecessors) == {a, b}


def test_workflow_config_cycle_detection_helper_should_report_cycle():
    node_a = SimpleNamespace(id=uuid4())
    node_b = SimpleNamespace(id=uuid4())
    adj = defaultdict(list, {node_a.id: [node_b.id], node_b.id: [node_a.id]})
    in_degree = defaultdict(int, {node_a.id: 1, node_b.id: 1})

    has_cycle = WorkflowConfig._is_cycle([node_a, node_b], adj, in_degree)

    assert has_cycle is True
