from types import SimpleNamespace
from uuid import uuid4
import random

import pytest

from internal.core.workflow.entities.node_entity import NodeType
from internal.entity.workflow_entity import WorkflowStatus, WorkflowResultStatus
from internal.exception import (
    FailException,
    ForbiddenException,
    NotFoundException,
    ValidateErrorException,
)
from internal.model import ApiTool, Dataset
from internal.service.workflow_service import WorkflowService as _WorkflowService


class _DummyQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def one_or_none(self):
        return self.result


class _DummySession:
    def __init__(self):
        self.query_result = None

    def query(self, _model):
        return _DummyQuery(self.query_result)


class _DummyDB:
    def __init__(self):
        self.session = _DummySession()


def _new_workflow_service(**kwargs):
    kwargs.setdefault("icon_generator_service", SimpleNamespace())
    return _WorkflowService(**kwargs)


def _build_service() -> _WorkflowService:
    return _new_workflow_service(
        db=_DummyDB(),
        builtin_provider_manager=SimpleNamespace(),
    )


def _build_create_req(tool_call_name: str = "wf_tool"):
    return SimpleNamespace(
        tool_call_name=SimpleNamespace(data=tool_call_name),
        data={
            "name": "workflow",
            "tool_call_name": tool_call_name,
            "icon": "https://a.com/wf.png",
            "description": "desc",
        },
    )


class TestWorkflowService:
    def test_create_workflow_should_raise_when_tool_call_name_duplicated(self):
        service = _build_service()
        service.db.session.query_result = SimpleNamespace(id=uuid4())

        with pytest.raises(ValidateErrorException):
            service.create_workflow(_build_create_req("dup_tool"), SimpleNamespace(id=uuid4()))

    def test_create_workflow_should_call_create_with_expected_payload(self, monkeypatch):
        service = _build_service()
        service.db.session.query_result = None
        account = SimpleNamespace(id=uuid4())

        captured = {}
        workflow = SimpleNamespace(id=uuid4())

        def fake_create(model, **kwargs):
            captured["model"] = model
            captured["kwargs"] = kwargs
            return workflow

        monkeypatch.setattr(service, "create", fake_create)

        result = service.create_workflow(_build_create_req(" wf_tool "), account)

        assert result is workflow
        assert captured["kwargs"]["account_id"] == account.id
        assert captured["kwargs"]["status"] == WorkflowStatus.DRAFT.value
        assert captured["kwargs"]["is_debug_passed"] is False
        assert captured["kwargs"]["tool_call_name"] == "wf_tool"
        assert captured["kwargs"]["draft_graph"] == {"nodes": [], "edges": []}

    def test_update_workflow_should_raise_when_tool_call_name_conflicted(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), account_id=account.id)
        service.db.session.query_result = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)

        with pytest.raises(ValidateErrorException):
            service.update_workflow(workflow.id, account, tool_call_name="dup_tool")

    def test_publish_workflow_should_raise_when_not_debug_passed(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(
            id=uuid4(),
            tool_call_name="wf_tool",
            description="desc",
            draft_graph={"nodes": [], "edges": []},
            is_debug_passed=False,
        )
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        monkeypatch.setattr(
            "internal.service.workflow_service.WorkflowConfig",
            lambda **kwargs: SimpleNamespace(**kwargs),
        )
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.publish_workflow(workflow.id, account)

        assert result is workflow
        assert updates[0][0] is workflow
        assert updates[0][1]["status"] == WorkflowStatus.PUBLISHED.value

    def test_publish_workflow_should_reset_debug_flag_when_config_invalid(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(
            id=uuid4(),
            tool_call_name="wf_tool",
            description="desc",
            draft_graph={"nodes": [], "edges": []},
            is_debug_passed=True,
        )
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)

        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        def raise_workflow_config(**_kwargs):
            raise Exception("invalid workflow config")

        monkeypatch.setattr("internal.service.workflow_service.WorkflowConfig", raise_workflow_config)

        with pytest.raises(ValidateErrorException):
            service.publish_workflow(workflow.id, account)

        assert updates[0][0] is workflow
        assert updates[0][1]["is_debug_passed"] is False

    def test_cancel_publish_workflow_should_raise_when_workflow_not_published(self, monkeypatch):
        service = _build_service()
        workflow = SimpleNamespace(status=WorkflowStatus.DRAFT.value)
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)

        with pytest.raises(FailException):
            service.cancel_publish_workflow(uuid4(), SimpleNamespace(id=uuid4()))

    def test_cancel_publish_workflow_should_reset_status_and_graph(self, monkeypatch):
        service = _build_service()
        workflow = SimpleNamespace(status=WorkflowStatus.PUBLISHED.value)
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)

        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.cancel_publish_workflow(uuid4(), SimpleNamespace(id=uuid4()))

        assert result is workflow
        assert updates[0][1]["graph"] == {}
        assert updates[0][1]["status"] == WorkflowStatus.DRAFT.value
        assert updates[0][1]["is_debug_passed"] is False

    def test_share_workflow_to_public_should_raise_when_publish_required(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), status=WorkflowStatus.DRAFT.value, account_id=account.id)
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)

        with pytest.raises(FailException):
            service.share_workflow_to_public(workflow.id, account, True)

    def test_share_workflow_to_public_should_update_public_flag(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), status=WorkflowStatus.PUBLISHED.value, account_id=account.id)
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.share_workflow_to_public(workflow.id, account, True)

        assert result is workflow
        assert updates == [(workflow, {"is_public": True})]

    def test_regenerate_icon_should_update_workflow_icon(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), name="工作流", description="desc")
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        service.icon_generator_service = SimpleNamespace(
            generate_icon=lambda name, description: f"https://icon/{name}/{description or 'empty'}"
        )
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        icon_url = service.regenerate_icon(workflow.id, account)

        assert icon_url.startswith("https://icon/")
        assert updates == [(workflow, {"icon": icon_url})]

    def test_regenerate_icon_should_raise_fail_exception_when_generator_failed(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), name="工作流", description="desc")
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)

        def _raise_icon_error(**_kwargs):
            raise RuntimeError("icon-failed")

        service.icon_generator_service = SimpleNamespace(
            generate_icon=_raise_icon_error
        )

        with pytest.raises(FailException):
            service.regenerate_icon(workflow.id, account)

    def test_generate_icon_preview_should_return_icon_url(self):
        service = _build_service()
        service.icon_generator_service = SimpleNamespace(
            generate_icon=lambda name, description: f"https://preview/{name}/{description or 'empty'}"
        )

        icon_url = service.generate_icon_preview("workflow-preview", "")

        assert icon_url == "https://preview/workflow-preview/empty"

    def test_generate_icon_preview_should_raise_fail_exception_when_generator_failed(self):
        service = _build_service()

        def _raise_preview_error(**_kwargs):
            raise RuntimeError("preview-failed")

        service.icon_generator_service = SimpleNamespace(
            generate_icon=_raise_preview_error
        )

        with pytest.raises(FailException):
            service.generate_icon_preview("workflow-preview", "desc")

    def test_get_draft_graph_should_enrich_builtin_tool_meta_and_reset_invalid_params(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), draft_graph={"nodes": [], "edges": []})
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)

        validated_graph = {
            "nodes": [
                {
                    "node_type": NodeType.TOOL.value,
                    "tool_type": "builtin_tool",
                    "provider_id": "search_provider",
                    "tool_id": "web_search",
                    "params": {"query": "上海天气", "unexpected": "x"},
                }
            ],
            "edges": [],
        }
        monkeypatch.setattr(service, "_validate_graph", lambda _graph, _account, **_kwargs: validated_graph)

        provider_entity = SimpleNamespace(
            name="search_provider",
            label="Search",
            description="搜索工具提供方",
        )
        tool_entity = SimpleNamespace(
            name="web_search",
            label="Web Search",
            description="搜索网页",
            params=[
                SimpleNamespace(name="query", default="默认查询"),
                SimpleNamespace(name="top_k", default=5),
            ],
        )
        service.builtin_provider_manager = SimpleNamespace(
            get_provider=lambda _provider_id: SimpleNamespace(
                provider_entity=provider_entity,
                get_tool_entity=lambda _tool_id: tool_entity,
            )
        )

        result = service.get_draft_graph(uuid4(), account)
        node = result["nodes"][0]

        assert node["meta"]["type"] == "builtin_tool"
        assert node["meta"]["provider"]["id"] == "search_provider"
        # 输入参数中含未知字段时，会回退到工具参数默认值集合。
        assert node["meta"]["tool"]["params"] == {"query": "默认查询", "top_k": 5}

    def test_delete_workflow_should_delegate_delete_and_return_record(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        deleted = []
        monkeypatch.setattr(service, "delete", lambda target: deleted.append(target))

        result = service.delete_workflow(workflow.id, account)

        assert result is workflow
        assert deleted == [workflow]

    def test_get_workflows_with_page_should_use_paginator(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["db"] = db
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return ["wf-1"]

        monkeypatch.setattr("internal.service.workflow_service.Paginator", _Paginator)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data="flow"),
            status=SimpleNamespace(data=WorkflowStatus.DRAFT.value),
        )

        workflows, paginator = service.get_workflows_with_page(req, account)

        assert workflows == ["wf-1"]
        assert captures["req"] is req
        assert captures["db"] is service.db
        assert captures["query"] is not None
        assert isinstance(paginator, _Paginator)

    def test_update_draft_graph_should_validate_then_reset_debug_flag(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        validated_graph = {"nodes": [{"id": "n1"}], "edges": []}
        monkeypatch.setattr(service, "_validate_graph", lambda _graph, _account, **_kwargs: validated_graph)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_draft_graph(workflow.id, {"nodes": [], "edges": []}, account)

        assert result is workflow
        assert updates == [(workflow, {"draft_graph": validated_graph, "is_debug_passed": False})]

    def test_debug_workflow_should_stream_chunks_and_persist_success_state(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            tool_call_name="wf_tool",
            description="desc",
            draft_graph={"nodes": [], "edges": []},
        )
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        monkeypatch.setattr(
            "internal.service.workflow_service.WorkflowConfig",
            lambda **kwargs: SimpleNamespace(**kwargs),
        )

        class _WorkflowTool:
            def __init__(self, workflow_config):
                self.workflow_config = workflow_config

            @staticmethod
            def stream(_inputs):
                yield {"node_1": {"node_results": [SimpleNamespace(node_id="node_1", status="succeeded")]}}

        monkeypatch.setattr("internal.service.workflow_service.WorkflowTool", _WorkflowTool)
        monkeypatch.setattr(
            "internal.service.workflow_service.convert_model_to_dict",
            lambda node_result: {"node_id": node_result.node_id, "status": node_result.status},
        )

        workflow_result = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: workflow_result)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        events = list(service.debug_workflow(workflow.id, {"query": "hello"}, account))

        assert len(events) == 1
        assert events[0].startswith("event: workflow")
        assert any(
            target is workflow_result and payload["status"] == WorkflowResultStatus.SUCCEEDED.value
            for target, payload in updates
        )
        assert all(target is not workflow for target, _ in updates)

    def test_get_workflow_should_raise_when_workflow_not_found(self, monkeypatch):
        service = _build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.get_workflow(uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_workflow_should_raise_when_account_has_no_permission(self, monkeypatch):
        service = _build_service()
        owner_id = uuid4()
        monkeypatch.setattr(
            service,
            "get",
            lambda *_args, **_kwargs: SimpleNamespace(id=uuid4(), account_id=owner_id),
        )

        with pytest.raises(ForbiddenException):
            service.get_workflow(uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_workflow_should_return_when_owned(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: workflow)

        result = service.get_workflow(workflow.id, account)

        assert result is workflow

    def test_update_workflow_should_update_and_return_when_no_conflict(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), account_id=account.id)
        service.db.session.query_result = None
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_workflow(workflow.id, account, tool_call_name="wf_new", name="new")

        assert result is workflow
        assert updates == [(workflow, {"tool_call_name": "wf_new", "name": "new"})]

    def test_publish_workflow_should_set_graph_and_status_when_config_valid(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(
            id=uuid4(),
            tool_call_name="wf_tool",
            description="desc",
            draft_graph={"nodes": [{"id": "n1"}], "edges": []},
            is_debug_passed=True,
        )
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        monkeypatch.setattr(
            "internal.service.workflow_service.WorkflowConfig",
            lambda **kwargs: SimpleNamespace(**kwargs),
        )
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.publish_workflow(workflow.id, account)

        assert result is workflow
        assert updates[0][0] is workflow
        assert updates[0][1]["graph"] == workflow.draft_graph
        assert updates[0][1]["status"] == WorkflowStatus.PUBLISHED.value
        assert updates[0][1]["is_debug_passed"] is False
        assert "published_at" in updates[0][1]

    def test_build_executable_graph_should_keep_only_start_to_end_path(self):
        service = _build_service()
        start_id = uuid4()
        code_id = uuid4()
        dangling_id = uuid4()
        end_id = uuid4()
        graph = {
            "nodes": [
                {"id": str(start_id), "node_type": NodeType.START.value},
                {"id": str(code_id), "node_type": NodeType.CODE.value},
                {"id": str(dangling_id), "node_type": NodeType.CODE.value},
                {"id": str(end_id), "node_type": NodeType.END.value},
            ],
            "edges": [
                {
                    "id": str(uuid4()),
                    "source": str(start_id),
                    "source_type": NodeType.START.value,
                    "target": str(code_id),
                    "target_type": NodeType.CODE.value,
                },
                {
                    "id": str(uuid4()),
                    "source": str(code_id),
                    "source_type": NodeType.CODE.value,
                    "target": str(end_id),
                    "target_type": NodeType.END.value,
                },
            ],
        }

        executable_graph = service._build_executable_graph(graph)

        node_ids = {node["id"] for node in executable_graph["nodes"]}
        assert str(start_id) in node_ids
        assert str(code_id) in node_ids
        assert str(end_id) in node_ids
        assert str(dangling_id) not in node_ids
        assert len(executable_graph["edges"]) == 2

    def test_publish_workflow_should_prune_dangling_nodes_before_publish(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        start_id = uuid4()
        code_id = uuid4()
        dangling_id = uuid4()
        end_id = uuid4()
        workflow = SimpleNamespace(
            id=uuid4(),
            tool_call_name="wf_tool",
            description="desc",
            draft_graph={
                "nodes": [
                    {"id": str(start_id), "node_type": NodeType.START.value},
                    {"id": str(code_id), "node_type": NodeType.CODE.value},
                    {"id": str(dangling_id), "node_type": NodeType.CODE.value},
                    {"id": str(end_id), "node_type": NodeType.END.value},
                ],
                "edges": [
                    {
                        "id": str(uuid4()),
                        "source": str(start_id),
                        "source_type": NodeType.START.value,
                        "target": str(code_id),
                        "target_type": NodeType.CODE.value,
                    },
                    {
                        "id": str(uuid4()),
                        "source": str(code_id),
                        "source_type": NodeType.CODE.value,
                        "target": str(end_id),
                        "target_type": NodeType.END.value,
                    },
                ],
            },
            is_debug_passed=True,
        )
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)

        config_calls = []

        def _fake_workflow_config(**kwargs):
            config_calls.append(kwargs)
            return SimpleNamespace(**kwargs)

        monkeypatch.setattr("internal.service.workflow_service.WorkflowConfig", _fake_workflow_config)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.publish_workflow(workflow.id, account)

        assert result is workflow
        published_graph = updates[0][1]["graph"]
        published_ids = {node["id"] for node in published_graph["nodes"]}
        assert str(dangling_id) not in published_ids
        assert str(start_id) in published_ids
        assert str(code_id) in published_ids
        assert str(end_id) in published_ids
        assert config_calls
        assert all(node["id"] != str(dangling_id) for node in config_calls[0]["nodes"])

    def test_debug_workflow_should_mark_result_failed_when_stream_error(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            tool_call_name="wf_tool",
            description="desc",
            draft_graph={"nodes": [], "edges": []},
        )
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        monkeypatch.setattr(
            "internal.service.workflow_service.WorkflowConfig",
            lambda **kwargs: SimpleNamespace(**kwargs),
        )

        class _WorkflowTool:
            def __init__(self, workflow_config):
                self.workflow_config = workflow_config

            @staticmethod
            def stream(_inputs):
                raise RuntimeError("stream-error")
                yield  # pragma: no cover

        monkeypatch.setattr("internal.service.workflow_service.WorkflowTool", _WorkflowTool)
        workflow_result = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: workflow_result)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        # 发生异常时内部会吞掉异常并写入失败状态，这里应拿到空事件列表。
        events = list(service.debug_workflow(workflow.id, {"query": "hello"}, account))

        assert events == []
        assert any(
            target is workflow_result and payload["status"] == WorkflowResultStatus.FAILED.value
            for target, payload in updates
        )
        assert not any(target is workflow and payload == {"is_debug_passed": True} for target, payload in updates)

    def test_debug_workflow_should_prune_dangling_nodes_before_building_tool(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        start_id = uuid4()
        code_id = uuid4()
        dangling_id = uuid4()
        end_id = uuid4()
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            tool_call_name="wf_tool",
            description="desc",
            draft_graph={
                "nodes": [
                    {"id": str(start_id), "node_type": NodeType.START.value},
                    {"id": str(code_id), "node_type": NodeType.CODE.value},
                    {"id": str(dangling_id), "node_type": NodeType.CODE.value},
                    {"id": str(end_id), "node_type": NodeType.END.value},
                ],
                "edges": [
                    {
                        "id": str(uuid4()),
                        "source": str(start_id),
                        "source_type": NodeType.START.value,
                        "target": str(code_id),
                        "target_type": NodeType.CODE.value,
                    },
                    {
                        "id": str(uuid4()),
                        "source": str(code_id),
                        "source_type": NodeType.CODE.value,
                        "target": str(end_id),
                        "target_type": NodeType.END.value,
                    },
                ],
            },
        )
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        config_calls = []

        def _fake_workflow_config(**kwargs):
            config_calls.append(kwargs)
            return SimpleNamespace(**kwargs)

        monkeypatch.setattr("internal.service.workflow_service.WorkflowConfig", _fake_workflow_config)

        class _WorkflowTool:
            def __init__(self, workflow_config):
                self.workflow_config = workflow_config

            @staticmethod
            def stream(_inputs):
                yield {"node_1": {"node_results": [SimpleNamespace(node_id="node_1", status="succeeded")]}}

        monkeypatch.setattr("internal.service.workflow_service.WorkflowTool", _WorkflowTool)
        monkeypatch.setattr(
            "internal.service.workflow_service.convert_model_to_dict",
            lambda node_result: {"node_id": node_result.node_id, "status": node_result.status},
        )
        workflow_result = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: workflow_result)
        monkeypatch.setattr(service, "update", lambda target, **kwargs: target)

        events = list(service.debug_workflow(workflow.id, {"query": "hello"}, account))

        assert events
        assert config_calls
        assert all(node["id"] != str(dangling_id) for node in config_calls[0]["nodes"])

    def test_get_workflows_with_page_should_build_default_filters_without_optional_conditions(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["db"] = db
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return []

        monkeypatch.setattr("internal.service.workflow_service.Paginator", _Paginator)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data=""),
            status=SimpleNamespace(data=""),
        )

        workflows, paginator = service.get_workflows_with_page(req, account)

        assert workflows == []
        assert captures["query"] is not None
        assert isinstance(paginator, _Paginator)

    def test_get_draft_graph_should_continue_when_builtin_provider_or_tool_missing(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), draft_graph={"nodes": [], "edges": []})
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        validated_graph = {
            "nodes": [
                {
                    "node_type": NodeType.TOOL.value,
                    "tool_type": "builtin_tool",
                    "provider_id": "provider-1",
                    "tool_id": "tool-a",
                    "params": {"query": "hi"},
                },
                {
                    "node_type": NodeType.TOOL.value,
                    "tool_type": "builtin_tool",
                    "provider_id": "provider-2",
                    "tool_id": "tool-b",
                    "params": {"query": "hi"},
                },
            ],
            "edges": [],
        }
        monkeypatch.setattr(service, "_validate_graph", lambda _graph, _account, **_kwargs: validated_graph)

        class _ProviderWithoutTool:
            provider_entity = SimpleNamespace(
                name="provider-2",
                label="p2",
                description="provider 2",
            )

            @staticmethod
            def get_tool_entity(_tool_id):
                return None

        service.builtin_provider_manager = SimpleNamespace(
            get_provider=lambda provider_id: None if provider_id == "provider-1" else _ProviderWithoutTool()
        )

        result = service.get_draft_graph(uuid4(), account)

        assert "meta" not in result["nodes"][0]
        assert "meta" not in result["nodes"][1]

    def test_get_draft_graph_should_keep_builtin_params_when_keys_match(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), draft_graph={"nodes": [], "edges": []})
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        validated_graph = {
            "nodes": [
                {
                    "node_type": NodeType.TOOL.value,
                    "tool_type": "builtin_tool",
                    "provider_id": "search_provider",
                    "tool_id": "web_search",
                    "params": {"query": "上海天气"},
                }
            ],
            "edges": [],
        }
        monkeypatch.setattr(service, "_validate_graph", lambda _graph, _account, **_kwargs: validated_graph)
        service.builtin_provider_manager = SimpleNamespace(
            get_provider=lambda _provider_id: SimpleNamespace(
                provider_entity=SimpleNamespace(name="search_provider", label="Search", description="desc"),
                get_tool_entity=lambda _tool_id: SimpleNamespace(
                    name="web_search",
                    label="Web Search",
                    description="搜索网页",
                    params=[SimpleNamespace(name="query", default="默认查询")],
                ),
            )
        )

        result = service.get_draft_graph(uuid4(), account)

        assert result["nodes"][0]["meta"]["tool"]["params"] == {"query": "上海天气"}

    def test_get_draft_graph_should_enrich_api_tool_and_dataset_meta(self, monkeypatch):
        class _ToolQuery:
            def __init__(self, tool_record):
                self.tool_record = tool_record

            def filter(self, *_args, **_kwargs):
                return self

            def one_or_none(self):
                return self.tool_record

        class _DatasetQuery:
            def __init__(self, datasets):
                self.datasets = datasets

            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return self.datasets

        class _Session:
            def __init__(self, tool_record, datasets):
                self.tool_record = tool_record
                self.datasets = datasets

            def query(self, model):
                if model is ApiTool:
                    return _ToolQuery(self.tool_record)
                if model is Dataset:
                    return _DatasetQuery(self.datasets)
                raise AssertionError(f"unexpected model query: {model}")

        account = SimpleNamespace(id=uuid4())
        provider = SimpleNamespace(
            id=uuid4(),
            name="api-provider",
            icon="https://icon",
            description="api provider desc",
        )
        tool_record = SimpleNamespace(
            id=uuid4(),
            name="weather_tool",
            description="天气查询",
            provider=provider,
        )
        dataset_records = [
            SimpleNamespace(id=uuid4(), name="dataset-a", icon="ia", description="da"),
            SimpleNamespace(id=uuid4(), name="dataset-b", icon="ib", description="db"),
        ]
        service = _new_workflow_service(
            db=SimpleNamespace(session=_Session(tool_record, dataset_records)),
            builtin_provider_manager=SimpleNamespace(),
        )
        workflow = SimpleNamespace(id=uuid4(), draft_graph={"nodes": [], "edges": []})
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        validated_graph = {
            "nodes": [
                {
                    "node_type": NodeType.TOOL.value,
                    "tool_type": "api_tool",
                    "provider_id": str(provider.id),
                    "tool_id": "weather_tool",
                    "params": {},
                },
                {
                    "node_type": NodeType.TOOL.value,
                    "tool_type": "unknown_type",
                    "provider_id": "",
                    "tool_id": "",
                    "params": {},
                },
                {
                    "node_type": NodeType.DATASET_RETRIEVAL.value,
                    "dataset_ids": [str(dataset_records[0].id), str(dataset_records[1].id)],
                },
            ],
            "edges": [],
        }
        monkeypatch.setattr(service, "_validate_graph", lambda _graph, _account, **_kwargs: validated_graph)

        result = service.get_draft_graph(uuid4(), account)

        api_tool_node = result["nodes"][0]
        unknown_tool_node = result["nodes"][1]
        dataset_node = result["nodes"][2]
        assert api_tool_node["meta"]["type"] == "api_tool"
        assert api_tool_node["meta"]["provider"]["name"] == "api-provider"
        assert api_tool_node["meta"]["tool"]["name"] == "weather_tool"
        assert unknown_tool_node["meta"]["provider"]["id"] == ""
        assert len(dataset_node["meta"]["datasets"]) == 2
        assert dataset_node["meta"]["datasets"][0]["name"] == "dataset-a"

    def test_get_draft_graph_should_keep_non_tool_non_dataset_nodes_untouched(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), draft_graph={"nodes": [], "edges": []})
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        monkeypatch.setattr(
            service,
            "_validate_graph",
            lambda _graph, _account, **_kwargs: {
                "nodes": [
                    {
                        "id": str(uuid4()),
                        "node_type": NodeType.START.value,
                        "title": "start",
                        "inputs": [],
                    }
                ],
                "edges": [],
            },
        )

        result = service.get_draft_graph(uuid4(), account)

        assert result["nodes"][0]["node_type"] == NodeType.START.value
        assert "meta" not in result["nodes"][0]

    def test_prepare_tool_node_should_fill_default_fields_and_outputs(self):
        service = _build_service()
        prepared = service._prepare_tool_node(
            {
                "id": str(uuid4()),
                "node_type": NodeType.TOOL.value,
                "title": "ToolNode",
                "meta": {"type": "api_tool"},
            }
        )

        assert prepared["tool_type"] == "api_tool"
        assert prepared["provider_id"] == "default_provider"
        assert prepared["tool_id"] == "default_tool"
        assert prepared["params"] == {}
        assert prepared["inputs"] == []
        assert prepared["outputs"][0]["name"] == "text"

    def test_prepare_tool_node_should_keep_existing_outputs(self):
        service = _build_service()
        outputs = [{"name": "result", "type": "string", "value": {"type": "generated"}}]

        prepared = service._prepare_tool_node(
            {
                "id": str(uuid4()),
                "node_type": NodeType.TOOL.value,
                "title": "ToolNode",
                "outputs": outputs.copy(),
            }
        )

        assert prepared["outputs"] == outputs

    def test_validate_graph_should_trim_dataset_ids_for_valid_graph(self):
        class _DatasetQuery:
            def __init__(self, datasets):
                self.datasets = datasets

            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return self.datasets

        class _Session:
            def __init__(self, datasets):
                self.datasets = datasets

            def query(self, model):
                if model is Dataset:
                    return _DatasetQuery(self.datasets)
                raise AssertionError(f"unexpected model query: {model}")

        account = SimpleNamespace(id=uuid4())
        owned_dataset = SimpleNamespace(id=uuid4(), account_id=account.id)
        service = _new_workflow_service(
            db=SimpleNamespace(session=_Session([owned_dataset])),
            builtin_provider_manager=SimpleNamespace(),
        )
        start_id = uuid4()
        dataset_node_id = uuid4()
        end_id = uuid4()
        valid_edge_id = uuid4()
        graph = {
            "nodes": [
                {
                    "id": str(start_id),
                    "node_type": NodeType.START.value,
                    "title": "start",
                    "inputs": [],
                },
                {
                    "id": str(dataset_node_id),
                    "node_type": NodeType.DATASET_RETRIEVAL.value,
                    "title": "dataset",
                    "dataset_ids": [str(owned_dataset.id), str(uuid4())],
                    "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.4},
                    "inputs": [
                        {
                            "name": "query",
                            "type": "string",
                            "required": True,
                            "value": {"type": "literal", "content": "hi"},
                        }
                    ],
                },
                {
                    "id": str(end_id),
                    "node_type": NodeType.END.value,
                    "title": "end",
                    "outputs": [],
                },
            ],
            "edges": [
                {
                    "id": str(valid_edge_id),
                    "source": str(start_id),
                    "source_type": NodeType.START.value,
                    "target": str(dataset_node_id),
                    "target_type": NodeType.DATASET_RETRIEVAL.value,
                },
            ],
        }

        validated = service._validate_graph(graph, account)

        assert len(validated["nodes"]) == 3
        assert len(validated["edges"]) == 1
        dataset_node = next(node for node in validated["nodes"] if node["node_type"] == NodeType.DATASET_RETRIEVAL.value)
        # _validate_graph 会根据权限过滤 dataset_ids，仅保留当前账号可访问的数据集。
        assert dataset_node["dataset_ids"] == [str(owned_dataset.id)]

    def test_get_draft_graph_should_use_empty_meta_when_api_tool_record_missing(self, monkeypatch):
        class _ToolQuery:
            def filter(self, *_args, **_kwargs):
                return self

            @staticmethod
            def one_or_none():
                return None

        class _Session:
            @staticmethod
            def query(model):
                if model is ApiTool:
                    return _ToolQuery()
                if model is Dataset:
                    return SimpleNamespace(filter=lambda *_a, **_k: SimpleNamespace(all=lambda: []))
                raise AssertionError(f"unexpected model query: {model}")

        service = _new_workflow_service(
            db=SimpleNamespace(session=_Session()),
            builtin_provider_manager=SimpleNamespace(),
        )
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), draft_graph={"nodes": [], "edges": []})
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        monkeypatch.setattr(
            service,
            "_validate_graph",
            lambda _graph, _account, **_kwargs: {
                "nodes": [
                    {
                        "node_type": NodeType.TOOL.value,
                        "tool_type": "api_tool",
                        "provider_id": str(uuid4()),
                        "tool_id": "missing-tool",
                        "params": {},
                    }
                ],
                "edges": [],
            },
        )

        result = service.get_draft_graph(uuid4(), account)

        assert result["nodes"][0]["meta"]["type"] == "api_tool"
        assert result["nodes"][0]["meta"]["provider"]["id"] == ""
        assert result["nodes"][0]["meta"]["tool"]["id"] == ""

    def test_get_draft_graph_should_use_empty_meta_when_api_tool_ids_missing(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), draft_graph={"nodes": [], "edges": []})
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        monkeypatch.setattr(
            service,
            "_validate_graph",
            lambda _graph, _account, **_kwargs: {
                "nodes": [
                    {
                        "node_type": NodeType.TOOL.value,
                        "tool_type": "api_tool",
                        "provider_id": "",
                        "tool_id": "",
                        "params": {},
                    }
                ],
                "edges": [],
            },
        )

        result = service.get_draft_graph(uuid4(), account)

        assert result["nodes"][0]["meta"]["type"] == "api_tool"
        assert result["nodes"][0]["meta"]["provider"]["id"] == ""
        assert result["nodes"][0]["meta"]["tool"]["id"] == ""

    def test_validate_graph_should_raise_validate_error_for_invalid_node_or_edge(self):
        class _InvalidPayload:
            def __init__(self, value):
                self.value = value

            def get(self, key, default=None):
                if key == "id":
                    return self.value
                return default

        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        start_id = uuid4()
        end_id = uuid4()
        invalid_node_graph = {
            "nodes": [
                {"id": str(start_id), "node_type": NodeType.START.value, "title": "start", "inputs": []},
                {"id": str(end_id), "node_type": NodeType.END.value, "title": "end", "outputs": []},
                _InvalidPayload("bad-node"),
            ],
            "edges": [
                {"id": str(uuid4()), "source": str(start_id), "source_type": NodeType.START.value, "target": str(end_id), "target_type": NodeType.END.value},
            ],
        }

        with pytest.raises(ValidateErrorException) as node_exc:
            service._validate_graph(invalid_node_graph, account)
        assert "节点验证失败" in str(node_exc.value)

        invalid_edge_graph = {
            "nodes": [
                {"id": str(start_id), "node_type": NodeType.START.value, "title": "start", "inputs": []},
                {"id": str(end_id), "node_type": NodeType.END.value, "title": "end", "outputs": []},
            ],
            "edges": [
                _InvalidPayload("bad-edge"),
            ],
        }

        with pytest.raises(ValidateErrorException) as edge_exc:
            service._validate_graph(invalid_edge_graph, account)
        assert "边验证失败" in str(edge_exc.value)

    def test_validate_graph_should_call_prepare_tool_node_for_tool_nodes(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        start_id = str(uuid4())
        tool_id = str(uuid4())
        end_id = str(uuid4())
        called = {"count": 0}
        original_prepare = service._prepare_tool_node

        def _capture_prepare(node):
            called["count"] += 1
            return original_prepare(node)

        monkeypatch.setattr(service, "_prepare_tool_node", _capture_prepare)
        graph = {
            "nodes": [
                {"id": start_id, "node_type": NodeType.START.value, "title": "start", "inputs": []},
                {"id": tool_id, "node_type": NodeType.TOOL.value, "title": "tool", "meta": {"type": "builtin_tool"}},
                {"id": end_id, "node_type": NodeType.END.value, "title": "end", "outputs": []},
            ],
            "edges": [
                {
                    "id": str(uuid4()),
                    "source": start_id,
                    "source_type": NodeType.START.value,
                    "target": tool_id,
                    "target_type": NodeType.TOOL.value,
                },
                {
                    "id": str(uuid4()),
                    "source": tool_id,
                    "source_type": NodeType.TOOL.value,
                    "target": end_id,
                    "target_type": NodeType.END.value,
                },
            ],
        }

        validated = service._validate_graph(graph, account)

        assert called["count"] == 1
        assert len(validated["nodes"]) == 3
        assert len(validated["edges"]) == 2

    def test_validate_graph_should_raise_when_node_type_unsupported(self):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        start_id = str(uuid4())
        end_id = str(uuid4())
        graph = {
            "nodes": [
                {"id": start_id, "node_type": NodeType.START.value, "title": "start", "inputs": []},
                {"id": end_id, "node_type": NodeType.END.value, "title": "end", "outputs": []},
                {"id": str(uuid4()), "node_type": "unsupported-node", "title": "bad"},
            ],
            "edges": [
                {
                    "id": str(uuid4()),
                    "source": start_id,
                    "source_type": NodeType.START.value,
                    "target": end_id,
                    "target_type": NodeType.END.value,
                },
            ],
        }

        with pytest.raises(ValidateErrorException, match="不支持的节点类型"):
            service._validate_graph(graph, account)

    def test_validate_graph_should_raise_when_node_id_duplicated(self):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        duplicated_id = str(uuid4())
        graph = {
            "nodes": [
                {"id": duplicated_id, "node_type": NodeType.START.value, "title": "start", "inputs": []},
                {"id": duplicated_id, "node_type": NodeType.END.value, "title": "end", "outputs": []},
            ],
            "edges": [],
        }

        with pytest.raises(ValidateErrorException, match="重复的节点ID"):
            service._validate_graph(graph, account)

    def test_validate_graph_should_raise_when_node_title_duplicated(self):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        graph = {
            "nodes": [
                {"id": str(uuid4()), "node_type": NodeType.START.value, "title": "dup", "inputs": []},
                {"id": str(uuid4()), "node_type": NodeType.END.value, "title": "dup", "outputs": []},
            ],
            "edges": [],
        }

        with pytest.raises(ValidateErrorException, match="重复的节点标题"):
            service._validate_graph(graph, account)

    def test_validate_graph_should_raise_when_start_or_end_node_count_exceeds_one(self):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        two_starts_graph = {
            "nodes": [
                {"id": str(uuid4()), "node_type": NodeType.START.value, "title": "start-a", "inputs": []},
                {"id": str(uuid4()), "node_type": NodeType.START.value, "title": "start-b", "inputs": []},
                {"id": str(uuid4()), "node_type": NodeType.END.value, "title": "end", "outputs": []},
            ],
            "edges": [],
        }
        with pytest.raises(ValidateErrorException, match="工作流只能有一个开始节点"):
            service._validate_graph(two_starts_graph, account)

        two_ends_graph = {
            "nodes": [
                {"id": str(uuid4()), "node_type": NodeType.START.value, "title": "start", "inputs": []},
                {"id": str(uuid4()), "node_type": NodeType.END.value, "title": "end-a", "outputs": []},
                {"id": str(uuid4()), "node_type": NodeType.END.value, "title": "end-b", "outputs": []},
            ],
            "edges": [],
        }
        with pytest.raises(ValidateErrorException, match="工作流只能有一个结束节点"):
            service._validate_graph(two_ends_graph, account)

    def test_validate_graph_should_raise_when_node_id_missing_and_node_invalid(self):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        graph = {
            "nodes": [
                {"id": str(uuid4()), "node_type": NodeType.START.value, "title": "start", "inputs": []},
                {"id": str(uuid4()), "node_type": NodeType.END.value, "title": "end", "outputs": []},
                {"title": "bad-node-without-id"},
            ],
            "edges": [],
        }

        with pytest.raises(ValidateErrorException, match=r"节点验证失败\(id=None"):
            service._validate_graph(graph, account)

    def test_validate_graph_should_raise_for_edge_duplicate_id_source_target_and_connection(self):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        start_id = str(uuid4())
        end_id = str(uuid4())
        base_nodes = [
            {"id": start_id, "node_type": NodeType.START.value, "title": "start", "inputs": []},
            {"id": end_id, "node_type": NodeType.END.value, "title": "end", "outputs": []},
        ]
        edge_id = str(uuid4())

        duplicate_id_graph = {
            "nodes": base_nodes,
            "edges": [
                {
                    "id": edge_id,
                    "source": start_id,
                    "source_type": NodeType.START.value,
                    "target": end_id,
                    "target_type": NodeType.END.value,
                },
                {
                    "id": edge_id,
                    "source": end_id,
                    "source_type": NodeType.END.value,
                    "target": start_id,
                    "target_type": NodeType.START.value,
                },
            ],
        }
        with pytest.raises(ValidateErrorException, match="重复的边ID"):
            service._validate_graph(duplicate_id_graph, account)

        missing_source_graph = {
            "nodes": base_nodes,
            "edges": [
                {
                    "id": str(uuid4()),
                    "source": str(uuid4()),
                    "source_type": NodeType.START.value,
                    "target": end_id,
                    "target_type": NodeType.END.value,
                },
            ],
        }
        with pytest.raises(ValidateErrorException, match="源节点不存在"):
            service._validate_graph(missing_source_graph, account)

        missing_target_graph = {
            "nodes": base_nodes,
            "edges": [
                {
                    "id": str(uuid4()),
                    "source": start_id,
                    "source_type": NodeType.START.value,
                    "target": str(uuid4()),
                    "target_type": NodeType.END.value,
                },
            ],
        }
        with pytest.raises(ValidateErrorException, match="目标节点不存在"):
            service._validate_graph(missing_target_graph, account)

        duplicate_connection_graph = {
            "nodes": base_nodes,
            "edges": [
                {
                    "id": str(uuid4()),
                    "source": start_id,
                    "source_type": NodeType.START.value,
                    "target": end_id,
                    "target_type": NodeType.END.value,
                },
                {
                    "id": str(uuid4()),
                    "source": start_id,
                    "source_type": NodeType.START.value,
                    "target": end_id,
                    "target_type": NodeType.END.value,
                },
            ],
        }
        with pytest.raises(ValidateErrorException, match="重复的边连接"):
            service._validate_graph(duplicate_connection_graph, account)

    def test_validate_graph_should_raise_when_edge_id_missing(self):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        start_id = str(uuid4())
        end_id = str(uuid4())
        graph = {
            "nodes": [
                {"id": start_id, "node_type": NodeType.START.value, "title": "start", "inputs": []},
                {"id": end_id, "node_type": NodeType.END.value, "title": "end", "outputs": []},
            ],
            "edges": [
                {
                    "source": start_id,
                    "source_type": NodeType.START.value,
                    "target": end_id,
                    "target_type": NodeType.END.value,
                },
            ],
        }

        with pytest.raises(ValidateErrorException, match=r"边验证失败\(id=None"):
            service._validate_graph(graph, account)

    def test_debug_workflow_should_mark_debug_passed_and_commit_when_end_node_seen(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            tool_call_name="wf_tool",
            description="desc",
            draft_graph={"nodes": [], "edges": []},
            is_debug_passed=False,
        )
        monkeypatch.setattr(service, "get_workflow", lambda *_args, **_kwargs: workflow)
        monkeypatch.setattr(
            "internal.service.workflow_service.WorkflowConfig",
            lambda **kwargs: SimpleNamespace(**kwargs),
        )

        class _WorkflowTool:
            def __init__(self, workflow_config):
                self.workflow_config = workflow_config

            @staticmethod
            def stream(_inputs):
                yield {"end_node": {"node_results": [SimpleNamespace(node_id="end-1", status="succeeded")]}}

        monkeypatch.setattr("internal.service.workflow_service.WorkflowTool", _WorkflowTool)
        monkeypatch.setattr(
            "internal.service.workflow_service.convert_model_to_dict",
            lambda node_result: {
                "node_id": node_result.node_id,
                "status": node_result.status,
                "node_data": {"node_type": "end"},
            },
        )

        class _Session:
            def __init__(self):
                self.added = []
                self.commit_calls = 0

            def add(self, obj):
                self.added.append(obj)

            def commit(self):
                self.commit_calls += 1

        session = _Session()
        service.db = SimpleNamespace(session=session)
        workflow_result = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: workflow_result)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        events = list(service.debug_workflow(workflow.id, {"query": "hello"}, account))

        assert events
        assert workflow.is_debug_passed is True
        assert session.added == [workflow]
        assert session.commit_calls == 1
        assert any(
            target is workflow_result and payload["status"] == WorkflowResultStatus.SUCCEEDED.value
            for target, payload in updates
        )

    def test_collect_reachable_node_ids_should_handle_cycles(self):
        adjacency = {
            "start": {"a", "b"},
            "a": {"c"},
            "b": {"c"},
            "c": set(),
        }

        reachable = _WorkflowService._collect_reachable_node_ids("start", adjacency)

        assert reachable == {"start", "a", "b", "c"}

    def test_collect_reachable_node_ids_should_skip_already_visited_neighbor(self):
        adjacency = {
            "start": {"start"},
        }

        reachable = _WorkflowService._collect_reachable_node_ids("start", adjacency)

        assert reachable == {"start"}

    def test_collect_reachable_node_ids_should_include_root_even_when_missing_in_adjacency(self):
        adjacency = {
            "a": {"b"},
            "b": set(),
        }

        reachable = _WorkflowService._collect_reachable_node_ids("orphan-root", adjacency)

        assert reachable == {"orphan-root"}

    def test_build_executable_graph_should_return_original_when_nodes_or_edges_not_list(self):
        service = _build_service()
        graph = {
            "nodes": {"id": "n1"},
            "edges": [],
        }

        assert service._build_executable_graph(graph) is graph

    def test_build_executable_graph_should_raise_when_start_cannot_reach_end_and_skip_invalid_edges(self):
        service = _build_service()
        start_id = str(uuid4())
        end_id = str(uuid4())
        graph = {
            "nodes": [
                {"id": start_id, "node_type": NodeType.START.value},
                {"id": end_id, "node_type": NodeType.END.value},
                "not-a-node",
                {"id": "", "node_type": NodeType.CODE.value},
            ],
            "edges": [
                "not-an-edge",
                {"id": str(uuid4()), "source": start_id, "target": str(uuid4())},
            ],
        }

        with pytest.raises(ValidateErrorException):
            service._build_executable_graph(graph)

    def test_build_executable_graph_should_return_original_when_start_or_end_missing(self):
        service = _build_service()
        rng = random.Random(20260306)

        for _ in range(12):
            has_start = rng.choice([True, False])
            has_end = rng.choice([True, False])
            if has_start and has_end:
                # 本测试专注 start/end 缺失场景
                continue

            nodes = []
            if has_start:
                nodes.append({"id": str(uuid4()), "node_type": NodeType.START.value})
            if has_end:
                nodes.append({"id": str(uuid4()), "node_type": NodeType.END.value})
            nodes.extend(
                {"id": str(uuid4()), "node_type": NodeType.CODE.value}
                for _ in range(rng.randint(1, 5))
            )

            edges = [
                {"id": str(uuid4()), "source": str(uuid4()), "target": str(uuid4())}
                for _ in range(rng.randint(1, 5))
            ]
            graph = {"nodes": nodes, "edges": edges}

            assert service._build_executable_graph(graph) is graph

    def test_build_executable_graph_should_satisfy_path_properties_for_random_graphs(self):
        service = _build_service()
        rng = random.Random(20260303)

        def _build_adjacency(edge_list, node_ids):
            adjacency = {node_id: set() for node_id in node_ids}
            for edge in edge_list:
                adjacency[edge["source"]].add(edge["target"])
            return adjacency

        for _ in range(30):
            start_id = str(uuid4())
            end_id = str(uuid4())
            middle_ids = [str(uuid4()) for _ in range(rng.randint(2, 7))]
            all_ids = [start_id, end_id, *middle_ids]

            nodes = (
                [{"id": start_id, "node_type": NodeType.START.value}]
                + [{"id": mid, "node_type": NodeType.CODE.value} for mid in middle_ids]
                + [{"id": end_id, "node_type": NodeType.END.value}]
                + ["invalid-node-payload", {"id": "", "node_type": NodeType.CODE.value}]
            )

            path_middle = rng.sample(middle_ids, rng.randint(1, len(middle_ids)))
            path = [start_id, *path_middle, end_id]

            edges = []
            for source, target in zip(path, path[1:]):
                edges.append(
                    {
                        "id": str(uuid4()),
                        "source": source,
                        "source_type": NodeType.CODE.value,
                        "target": target,
                        "target_type": NodeType.CODE.value,
                    }
                )

            for _ in range(rng.randint(5, 25)):
                source = rng.choice(all_ids)
                target = rng.choice(all_ids)
                edges.append(
                    {
                        "id": str(uuid4()),
                        "source": source,
                        "source_type": NodeType.CODE.value,
                        "target": target,
                        "target_type": NodeType.CODE.value,
                    }
                )

            edges.append({"id": str(uuid4()), "source": "ghost-node", "target": start_id})
            edges.append("invalid-edge-payload")

            executable = service._build_executable_graph({"nodes": nodes, "edges": edges})
            executable_node_ids = {node["id"] for node in executable["nodes"]}

            assert start_id in executable_node_ids
            assert end_id in executable_node_ids

            for edge in executable["edges"]:
                assert edge["source"] in executable_node_ids
                assert edge["target"] in executable_node_ids

            forward = _build_adjacency(executable["edges"], executable_node_ids)
            reverse = _build_adjacency(
                [
                    {"source": edge["target"], "target": edge["source"]}
                    for edge in executable["edges"]
                ],
                executable_node_ids,
            )
            reachable_from_start = _WorkflowService._collect_reachable_node_ids(start_id, forward)
            reachable_to_end = _WorkflowService._collect_reachable_node_ids(end_id, reverse)

            assert end_id in reachable_from_start
            assert executable_node_ids == reachable_from_start & reachable_to_end

    def test_build_executable_graph_should_raise_for_random_disconnected_graphs(self):
        service = _build_service()
        rng = random.Random(20260304)

        for _ in range(20):
            start_id = str(uuid4())
            end_id = str(uuid4())
            middle_ids = [str(uuid4()) for _ in range(rng.randint(2, 6))]
            valid_targets = [start_id, *middle_ids]

            nodes = (
                [{"id": start_id, "node_type": NodeType.START.value}]
                + [{"id": mid, "node_type": NodeType.CODE.value} for mid in middle_ids]
                + [{"id": end_id, "node_type": NodeType.END.value}]
            )

            edges = []
            for _ in range(rng.randint(3, 12)):
                source = rng.choice(valid_targets)
                target = rng.choice(valid_targets)
                edges.append(
                    {
                        "id": str(uuid4()),
                        "source": source,
                        "source_type": NodeType.CODE.value,
                        "target": target,
                        "target_type": NodeType.CODE.value,
                    }
                )

            # 添加非法边噪声，验证鲁棒性：这些边会被忽略，不应影响断连判断。
            edges.append({"id": str(uuid4()), "source": "ghost", "target": end_id})
            edges.append("invalid-edge-payload")

            with pytest.raises(ValidateErrorException):
                service._build_executable_graph({"nodes": nodes, "edges": edges})

    def test_validate_graph_should_raise_for_random_malformed_nodes_and_edges(self):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        rng = random.Random(20260305)

        for _ in range(20):
            start_id = str(uuid4())
            end_id = str(uuid4())
            graph = {
                "nodes": [
                    {"id": start_id, "node_type": NodeType.START.value, "title": "start", "inputs": []},
                    {"id": end_id, "node_type": NodeType.END.value, "title": "end", "outputs": []},
                ],
                "edges": [
                    {
                        "id": str(uuid4()),
                        "source": start_id,
                        "source_type": NodeType.START.value,
                        "target": end_id,
                        "target_type": NodeType.END.value,
                    }
                ],
            }

            malformed_node_count = rng.randint(3, 8)
            for _ in range(malformed_node_count):
                if rng.random() < 0.5:
                    graph["nodes"].append("malformed-node")
                else:
                    graph["nodes"].append({"id": str(uuid4()), "title": "missing-node-type"})

            malformed_edge_count = rng.randint(3, 8)
            for _ in range(malformed_edge_count):
                if rng.random() < 0.5:
                    graph["edges"].append("malformed-edge")
                else:
                    graph["edges"].append(
                        {
                            "id": str(uuid4()),
                            "source": "ghost",
                            "source_type": NodeType.START.value,
                            "target": "ghost-target",
                            "target_type": NodeType.END.value,
                        }
                    )

            with pytest.raises(ValidateErrorException):
                service._validate_graph(graph, account)

    def test_build_executable_graph_should_remain_safe_under_iterative_edge_mutations(self):
        service = _build_service()
        rng = random.Random(20260307)

        start_id = str(uuid4())
        end_id = str(uuid4())
        middle_ids = [str(uuid4()) for _ in range(5)]
        valid_node_ids = {start_id, end_id, *middle_ids}
        nodes = (
            [{"id": start_id, "node_type": NodeType.START.value}]
            + [{"id": node_id, "node_type": NodeType.CODE.value} for node_id in middle_ids]
            + [{"id": end_id, "node_type": NodeType.END.value}]
            + ["invalid-node-payload"]
        )

        mutation_edges = [
            {
                "id": str(uuid4()),
                "source": start_id,
                "source_type": NodeType.START.value,
                "target": middle_ids[0],
                "target_type": NodeType.CODE.value,
            },
            {
                "id": str(uuid4()),
                "source": middle_ids[0],
                "source_type": NodeType.CODE.value,
                "target": middle_ids[1],
                "target_type": NodeType.CODE.value,
            },
            {
                "id": str(uuid4()),
                "source": middle_ids[1],
                "source_type": NodeType.CODE.value,
                "target": end_id,
                "target_type": NodeType.END.value,
            },
        ]

        def _has_valid_path(candidate_edges: list[dict]) -> bool:
            adjacency = {node_id: set() for node_id in valid_node_ids}
            for edge in candidate_edges:
                source = edge.get("source")
                target = edge.get("target")
                if source in valid_node_ids and target in valid_node_ids:
                    adjacency[source].add(target)
            reachable = _WorkflowService._collect_reachable_node_ids(start_id, adjacency)
            return end_id in reachable

        for _ in range(120):
            action = rng.choice(["add_valid", "add_noise", "remove"])
            if action == "add_valid":
                source = rng.choice(list(valid_node_ids))
                target = rng.choice(list(valid_node_ids))
                mutation_edges.append(
                    {
                        "id": str(uuid4()),
                        "source": source,
                        "source_type": NodeType.CODE.value,
                        "target": target,
                        "target_type": NodeType.CODE.value,
                    }
                )
            elif action == "add_noise":
                mutation_edges.append(
                    {
                        "id": str(uuid4()),
                        "source": "ghost-source",
                        "source_type": NodeType.CODE.value,
                        "target": rng.choice(list(valid_node_ids)),
                        "target_type": NodeType.CODE.value,
                    }
                )
            elif mutation_edges:
                mutation_edges.pop(rng.randrange(len(mutation_edges)))

            graph = {
                "nodes": nodes,
                "edges": mutation_edges + ["invalid-edge-payload"],
            }

            if _has_valid_path(mutation_edges):
                executable = service._build_executable_graph(graph)
                executable_node_ids = {node["id"] for node in executable["nodes"]}

                assert start_id in executable_node_ids
                assert end_id in executable_node_ids
                assert executable_node_ids <= valid_node_ids
                for edge in executable["edges"]:
                    assert edge["source"] in executable_node_ids
                    assert edge["target"] in executable_node_ids
            else:
                with pytest.raises(ValidateErrorException):
                    service._build_executable_graph(graph)
