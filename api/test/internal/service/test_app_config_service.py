from contextlib import contextmanager
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
import json

import pytest
from werkzeug.datastructures import FileStorage

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.entity.app_entity import DEFAULT_APP_CONFIG
from internal.entity.conversation_entity import InvokeFrom
from internal.entity.workflow_entity import WorkflowStatus
from internal.exception import FailException, NotFoundException
from internal.model import ApiTool, AppDatasetJoin, Dataset, Message, Workflow
from internal.service.app_config_service import AppConfigService
from internal.service.assistant_agent_service import AssistantAgentService
from internal.service.cos_service import CosService
from internal.service.embeddings_service import EmbeddingsService
from internal.service.faiss_service import FaissService
from internal.service.upload_file_service import UploadFileService
from internal.service.vector_database_service import VectorDatabaseService


@contextmanager
def _null_context():
    yield


class _QueryStub:
    def __init__(self, *, all_result=None):
        self._all_result = all_result if all_result is not None else []

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._all_result


class TestAppConfigService:
    def _build_service(self, language_model_manager=None, builtin_provider_manager=None, api_provider_manager=None, session=None):
        return AppConfigService(
            db=SimpleNamespace(session=session or SimpleNamespace(query=lambda _model: _QueryStub(all_result=[])), auto_commit=lambda: _null_context()),
            api_provider_manager=api_provider_manager or SimpleNamespace(get_tool=lambda _entity: "api-tool-instance"),
            language_model_manager=language_model_manager or SimpleNamespace(get_provider=lambda _provider: None),
            builtin_provider_manager=builtin_provider_manager or SimpleNamespace(get_tool=lambda _pid, _name: None),
        )

    def test_process_and_validate_model_config_should_fallback_to_default_when_provider_invalid(self):
        service = self._build_service()

        result = service._process_and_validate_model_config(
            {"provider": "missing-provider", "model": "gpt-x", "parameters": {}}
        )

        assert result == DEFAULT_APP_CONFIG["model_config"]

    def test_process_and_validate_model_config_should_normalize_invalid_parameters(self):
        parameters = [
            SimpleNamespace(
                name="temperature",
                default=0.7,
                required=True,
                type=SimpleNamespace(value="float"),
                options=[],
                min=0.0,
                max=1.0,
            ),
            SimpleNamespace(
                name="mode",
                default="balanced",
                required=False,
                type=SimpleNamespace(value="string"),
                options=["balanced", "creative"],
                min=None,
                max=None,
            ),
        ]
        provider = SimpleNamespace(
            get_model_entity=lambda _model: SimpleNamespace(parameters=parameters)
        )
        service = self._build_service(
            language_model_manager=SimpleNamespace(get_provider=lambda _provider: provider)
        )

        result = service._process_and_validate_model_config(
            {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "parameters": {"temperature": "bad", "mode": "unknown", "extra": 1},
            }
        )

        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4o-mini"
        assert result["parameters"]["temperature"] == 0.7
        assert result["parameters"]["mode"] == "balanced"
        assert "extra" not in result["parameters"]

    def test_get_langchain_tools_by_tools_config_should_build_builtin_and_api_tools(self, monkeypatch):
        builtin_manager = SimpleNamespace(
            get_tool=lambda provider_id, tool_name: (
                lambda **params: {
                    "kind": "builtin",
                    "provider": provider_id,
                    "tool": tool_name,
                    "params": params,
                }
            )
        )
        service = self._build_service(
            builtin_provider_manager=builtin_manager,
            api_provider_manager=SimpleNamespace(
                get_tool=lambda tool_entity: {"kind": "api", "name": tool_entity.name, "url": tool_entity.url}
            ),
        )
        api_tool_record = SimpleNamespace(
            id=uuid4(),
            name="weather",
            url="https://api.example.com/weather",
            method="get",
            description="查询天气",
            parameters=[{"name": "city"}],
            provider=SimpleNamespace(headers=[{"key": "Authorization", "value": "Bearer x"}]),
        )
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: api_tool_record if model is ApiTool else None,
        )

        tools = service.get_langchain_tools_by_tools_config(
            [
                {
                    "type": "builtin_tool",
                    "provider": {"id": "search_provider"},
                    "tool": {"name": "web_search", "params": {"query": "上海天气"}},
                },
                {
                    "type": "api_tool",
                    "tool": {"id": str(uuid4())},
                },
            ]
        )

        assert tools[0]["kind"] == "builtin"
        assert tools[0]["params"]["query"] == "上海天气"
        assert tools[1]["kind"] == "api"
        assert tools[1]["name"] == "weather"

    def test_get_langchain_tools_by_workflow_ids_should_skip_invalid_workflows(self, monkeypatch):
        account_id = uuid4()
        start_node_id = uuid4()
        end_node_id = uuid4()
        edge_id = uuid4()
        workflow_ok = SimpleNamespace(
            account_id=account_id,
            tool_call_name="weather_lookup",
            description="查询天气工作流",
            graph={
                "nodes": [
                    {
                        "id": str(start_node_id),
                        "node_type": "start",
                        "title": "开始",
                        "position": {"x": 0, "y": 0},
                        "inputs": [],
                    },
                    {
                        "id": str(end_node_id),
                        "node_type": "end",
                        "title": "结束",
                        "position": {"x": 200, "y": 0},
                        "outputs": [],
                    },
                ],
                "edges": [
                    {
                        "id": str(edge_id),
                        "source": str(start_node_id),
                        "source_type": "start",
                        "target": str(end_node_id),
                        "target_type": "end",
                    }
                ],
            },
        )
        # graph 为 None 会触发 .get 异常，验证该坏数据会被忽略而不影响其他工作流。
        workflow_invalid = SimpleNamespace(
            account_id=account_id,
            tool_call_name="broken",
            description="invalid",
            graph=None,
        )

        class _WorkflowQuery:
            def __init__(self, records):
                self._records = records

            def filter(self, *_args, **_kwargs):
                return self

            def __iter__(self):
                return iter(self._records)

        service = self._build_service(
            session=SimpleNamespace(query=lambda _model: _WorkflowQuery([workflow_ok, workflow_invalid]))
        )
        workflow_configs = []

        class _WorkflowToolStub:
            def __init__(self, workflow_config):
                workflow_configs.append(workflow_config)

        monkeypatch.setattr("internal.service.app_config_service.WorkflowTool", _WorkflowToolStub)

        tools = service.get_langchain_tools_by_workflow_ids([uuid4(), uuid4()])

        assert len(tools) == 1
        assert isinstance(tools[0], _WorkflowToolStub)
        assert workflow_configs[0].name == "wf_weather_lookup"
        assert workflow_configs[0].description == "查询天气工作流"

    def test_get_app_config_should_sync_invalid_refs_and_return_transformed_payload(self, monkeypatch):
        """覆盖 get_app_config 的关键分支:
        1. model/tools/workflows 与校验结果不一致时会触发 update
        2. app_dataset_joins 中失效知识库会被删除
        3. 返回值应使用校验后的 model/tools/workflows/datasets 组装
        """

        keep_dataset_id = uuid4()
        remove_dataset_id = uuid4()

        class _DeleteQuery:
            def __init__(self):
                self.deleted = False

            def filter(self, *_args, **_kwargs):
                return self

            def delete(self):
                self.deleted = True

        delete_query = _DeleteQuery()

        class _Session:
            def query(self, model):
                if model is AppDatasetJoin:
                    return delete_query
                return _QueryStub(all_result=[])

        auto_commit_calls = []

        @contextmanager
        def _auto_commit():
            auto_commit_calls.append(True)
            yield

        service = AppConfigService(
            db=SimpleNamespace(session=_Session(), auto_commit=_auto_commit),
            api_provider_manager=SimpleNamespace(get_tool=lambda _entity: "api-tool-instance"),
            language_model_manager=SimpleNamespace(get_provider=lambda _provider: None),
            builtin_provider_manager=SimpleNamespace(get_tool=lambda _pid, _name: None),
        )

        app_config = SimpleNamespace(
            id=uuid4(),
            model_config={"provider": "legacy"},
            tools=[{"type": "api_tool", "tool_id": "legacy"}],
            app_dataset_joins=[
                SimpleNamespace(dataset_id=keep_dataset_id),
                SimpleNamespace(dataset_id=remove_dataset_id),
            ],
            workflows=["wf-legacy"],
            dialog_round=3,
            preset_prompt="prompt",
            retrieval_config={"strategy": "semantic"},
            long_term_memory={"enable": True},
            opening_statement="hello",
            opening_questions=["q1"],
            speech_to_text={"enable": False},
            text_to_speech={"enable": False},
            suggested_after_answer={"enable": True},
            review_config={"enable": False},
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
            created_at=datetime(2024, 1, 1, 0, 0, 0),
        )
        app = SimpleNamespace(app_config=app_config)

        monkeypatch.setattr(
            service,
            "_process_and_validate_model_config",
            lambda _config: {"provider": "openai", "model": "gpt-4o-mini", "parameters": {}},
        )
        monkeypatch.setattr(
            service,
            "_process_and_validate_tools",
            lambda _tools: (
                [{"type": "builtin_tool", "tool": {"name": "web_search"}}],
                [{"type": "builtin_tool", "provider_id": "search", "tool_id": "web_search", "params": {}}],
            ),
        )
        monkeypatch.setattr(
            service,
            "_process_and_validate_datasets",
            lambda _dataset_ids: (
                [{"id": str(keep_dataset_id), "name": "知识库A", "icon": "", "description": ""}],
                [str(keep_dataset_id)],
            ),
        )
        monkeypatch.setattr(
            service,
            "_process_and_validate_workflows",
            lambda _workflows: (
                [{"id": "wf-new", "name": "新工作流"}],
                ["wf-new"],
            ),
        )

        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.get_app_config(app)

        assert delete_query.deleted is True
        assert len(auto_commit_calls) == 1
        assert any("model_config" in payload for _, payload in updates)
        assert any("tools" in payload for _, payload in updates)
        assert any("workflows" in payload for _, payload in updates)
        assert result["model_config"]["provider"] == "openai"
        assert result["tools"][0]["type"] == "builtin_tool"
        assert result["workflows"][0]["id"] == "wf-new"
        assert result["datasets"][0]["id"] == str(keep_dataset_id)

    def test_get_draft_app_config_should_sync_invalid_refs_and_return_transformed_payload(self, monkeypatch):
        service = self._build_service()
        keep_dataset_id = uuid4()

        draft_app_config = SimpleNamespace(
            id=uuid4(),
            model_config={"provider": "legacy"},
            tools=[{"type": "api_tool", "tool_id": "legacy"}],
            datasets=["to-remove", str(keep_dataset_id)],
            workflows=["wf-legacy"],
            dialog_round=3,
            preset_prompt="prompt",
            retrieval_config={"strategy": "semantic"},
            long_term_memory={"enable": True},
            opening_statement="hello",
            opening_questions=["q1"],
            speech_to_text={"enable": False},
            text_to_speech={"enable": False},
            suggested_after_answer={"enable": True},
            review_config={"enable": False},
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
            created_at=datetime(2024, 1, 1, 0, 0, 0),
        )
        app = SimpleNamespace(draft_app_config=draft_app_config)

        monkeypatch.setattr(
            service,
            "_process_and_validate_model_config",
            lambda _config: {"provider": "openai", "model": "gpt-4o-mini", "parameters": {}},
        )
        monkeypatch.setattr(
            service,
            "_process_and_validate_tools",
            lambda _tools: (
                [{"type": "builtin_tool", "tool": {"name": "web_search"}}],
                [{"type": "builtin_tool", "provider_id": "search", "tool_id": "web_search", "params": {}}],
            ),
        )
        monkeypatch.setattr(
            service,
            "_process_and_validate_datasets",
            lambda _dataset_ids: (
                [{"id": str(keep_dataset_id), "name": "知识库A", "icon": "", "description": ""}],
                [str(keep_dataset_id)],
            ),
        )
        monkeypatch.setattr(
            service,
            "_process_and_validate_workflows",
            lambda _workflows: (
                [{"id": "wf-new", "name": "新工作流"}],
                ["wf-new"],
            ),
        )

        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.get_draft_app_config(app)

        assert any("model_config" in payload for _, payload in updates)
        assert any("tools" in payload for _, payload in updates)
        assert any("datasets" in payload for _, payload in updates)
        assert any("workflows" in payload for _, payload in updates)
        assert result["model_config"]["provider"] == "openai"
        assert result["tools"][0]["type"] == "builtin_tool"
        assert result["workflows"][0]["id"] == "wf-new"
        assert result["datasets"][0]["id"] == str(keep_dataset_id)

    def test_get_draft_app_config_should_skip_updates_when_validated_values_unchanged(self, monkeypatch):
        service = self._build_service()
        dataset_id = str(uuid4())
        workflow_id = str(uuid4())
        model_config = {"provider": "openai", "model": "gpt-4o-mini", "parameters": {}}
        tools_config = [{"type": "builtin_tool", "provider_id": "search", "tool_id": "web_search", "params": {"query": "hi"}}]
        draft_app_config = SimpleNamespace(
            id=uuid4(),
            model_config=model_config,
            tools=tools_config,
            datasets=[dataset_id],
            workflows=[workflow_id],
            dialog_round=3,
            preset_prompt="prompt",
            retrieval_config={"strategy": "semantic"},
            long_term_memory={"enable": True},
            opening_statement="hello",
            opening_questions=["q1"],
            speech_to_text={"enable": False},
            text_to_speech={"enable": False},
            suggested_after_answer={"enable": True},
            review_config={"enable": False},
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
            created_at=datetime(2024, 1, 1, 0, 0, 0),
        )
        app = SimpleNamespace(draft_app_config=draft_app_config)

        monkeypatch.setattr(service, "_process_and_validate_model_config", lambda _config: model_config)
        monkeypatch.setattr(
            service,
            "_process_and_validate_tools",
            lambda _tools: ([{"type": "builtin_tool"}], tools_config),
        )
        monkeypatch.setattr(
            service,
            "_process_and_validate_datasets",
            lambda _dataset_ids: ([{"id": dataset_id, "name": "知识库A", "icon": "", "description": ""}], [dataset_id]),
        )
        monkeypatch.setattr(
            service,
            "_process_and_validate_workflows",
            lambda _workflows: ([{"id": workflow_id, "name": "工作流A"}], [workflow_id]),
        )
        updates = []
        monkeypatch.setattr(service, "update", lambda target, **kwargs: updates.append((target, kwargs)) or target)

        result = service.get_draft_app_config(app)

        assert updates == []
        assert result["model_config"] == model_config

    def test_get_app_config_should_skip_updates_and_dataset_cleanup_when_valid(self, monkeypatch):
        dataset_id = str(uuid4())
        workflow_id = "wf-1"
        model_config = {"provider": "openai", "model": "gpt-4o-mini", "parameters": {}}
        tools_config = [{"type": "builtin_tool", "provider_id": "search", "tool_id": "web_search", "params": {"query": "hi"}}]

        class _Session:
            def query(self, _model):
                return _QueryStub()

        service = AppConfigService(
            db=SimpleNamespace(session=_Session(), auto_commit=lambda: _null_context()),
            api_provider_manager=SimpleNamespace(get_tool=lambda _entity: "api-tool-instance"),
            language_model_manager=SimpleNamespace(get_provider=lambda _provider: None),
            builtin_provider_manager=SimpleNamespace(get_tool=lambda _pid, _name: None),
        )
        app_config = SimpleNamespace(
            id=uuid4(),
            model_config=model_config,
            tools=tools_config,
            app_dataset_joins=[SimpleNamespace(dataset_id=dataset_id)],
            workflows=[workflow_id],
            dialog_round=3,
            preset_prompt="prompt",
            retrieval_config={"strategy": "semantic"},
            long_term_memory={"enable": True},
            opening_statement="hello",
            opening_questions=["q1"],
            speech_to_text={"enable": False},
            text_to_speech={"enable": False},
            suggested_after_answer={"enable": True},
            review_config={"enable": False},
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
            created_at=datetime(2024, 1, 1, 0, 0, 0),
        )
        app = SimpleNamespace(app_config=app_config)
        monkeypatch.setattr(service, "_process_and_validate_model_config", lambda _config: model_config)
        monkeypatch.setattr(
            service,
            "_process_and_validate_tools",
            lambda _tools: ([{"type": "builtin_tool"}], tools_config),
        )
        monkeypatch.setattr(
            service,
            "_process_and_validate_datasets",
            lambda _dataset_ids: ([{"id": dataset_id, "name": "知识库A", "icon": "", "description": ""}], [dataset_id]),
        )
        monkeypatch.setattr(
            service,
            "_process_and_validate_workflows",
            lambda _workflows: ([{"id": workflow_id, "name": "工作流A"}], [workflow_id]),
        )
        updates = []
        monkeypatch.setattr(service, "update", lambda target, **kwargs: updates.append((target, kwargs)) or target)

        result = service.get_app_config(app)

        assert updates == []
        assert result["model_config"] == model_config

    def test_get_langchain_tools_by_tools_config_should_skip_missing_tools(self, monkeypatch):
        service = self._build_service(
            builtin_provider_manager=SimpleNamespace(get_tool=lambda _pid, _name: None),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        tools = service.get_langchain_tools_by_tools_config(
            [
                {
                    "type": "builtin_tool",
                    "provider": {"id": "builtin-provider"},
                    "tool": {"name": "missing-tool", "params": {"q": "x"}},
                },
                {
                    "type": "api_tool",
                    "tool": {"id": str(uuid4())},
                },
            ]
        )

        assert tools == []

    def test_process_and_validate_tools_should_filter_invalid_and_normalize_params(self):
        tool_entity = SimpleNamespace(
            name="web_search",
            label="网页搜索",
            description="用于检索网页内容",
            params=[
                SimpleNamespace(name="query", default=""),
                SimpleNamespace(name="top_k", default=3),
            ],
        )
        provider_entity = SimpleNamespace(name="search", label="搜索", description="内置搜索工具")
        builtin_provider = SimpleNamespace(
            provider_entity=provider_entity,
            get_tool_entity=lambda tool_id: tool_entity if tool_id == "web_search" else None,
        )
        builtin_provider_manager = SimpleNamespace(
            get_provider=lambda provider_id: (
                builtin_provider if provider_id == "search" else
                SimpleNamespace(provider_entity=provider_entity, get_tool_entity=lambda _tool_id: None)
                if provider_id == "search-no-tool"
                else None
            )
        )

        api_tool_record = SimpleNamespace(
            id=uuid4(),
            name="weather",
            description="天气查询",
            provider=SimpleNamespace(id=uuid4(), name="weather-api", icon="icon.png", description="天气API"),
        )

        class _ApiToolQuery:
            def __init__(self, results):
                self._results = results

            def filter(self, *_args, **_kwargs):
                return self

            def one_or_none(self):
                return self._results.pop(0)

        class _Session:
            def __init__(self):
                self._results = [api_tool_record, None]

            def query(self, model):
                assert model is ApiTool
                return _ApiToolQuery(self._results)

        service = self._build_service(
            builtin_provider_manager=builtin_provider_manager,
            session=_Session(),
        )

        tools, validate_tools = service._process_and_validate_tools(
            [
                {
                    "type": "builtin_tool",
                    "provider_id": "search",
                    "tool_id": "web_search",
                    "params": {"unexpected": "value"},
                },
                {
                    "type": "builtin_tool",
                    "provider_id": "missing-provider",
                    "tool_id": "web_search",
                    "params": {"query": "ignored"},
                },
                {
                    "type": "builtin_tool",
                    "provider_id": "search-no-tool",
                    "tool_id": "missing-tool",
                    "params": {"query": "ignored"},
                },
                {
                    "type": "api_tool",
                    "provider_id": str(uuid4()),
                    "tool_id": "weather",
                    "params": {},
                },
                {
                    "type": "api_tool",
                    "provider_id": str(uuid4()),
                    "tool_id": "not-found",
                    "params": {},
                },
            ]
        )

        assert len(validate_tools) == 2
        assert validate_tools[0]["params"] == {"query": "", "top_k": 3}
        assert validate_tools[1]["type"] == "api_tool"
        assert tools[0]["tool"]["params"] == {"query": "", "top_k": 3}
        assert tools[1]["type"] == "api_tool"
        assert tools[1]["tool"]["id"] == str(api_tool_record.id)

    def test_process_and_validate_tools_should_keep_params_and_ignore_unknown_type(self):
        tool_entity = SimpleNamespace(
            name="web_search",
            label="网页搜索",
            description="用于检索网页内容",
            params=[SimpleNamespace(name="query", default="")],
        )
        provider_entity = SimpleNamespace(name="search", label="搜索", description="内置搜索工具")
        provider = SimpleNamespace(
            provider_entity=provider_entity,
            get_tool_entity=lambda _tool_id: tool_entity,
        )
        service = self._build_service(
            builtin_provider_manager=SimpleNamespace(get_provider=lambda _provider_id: provider),
            session=SimpleNamespace(query=lambda _model: _QueryStub(one_or_none_result=None)),
        )

        tools, validate_tools = service._process_and_validate_tools(
            [
                {
                    "type": "builtin_tool",
                    "provider_id": "search",
                    "tool_id": "web_search",
                    "params": {"query": "hello"},
                },
                {
                    "type": "unsupported_tool_type",
                    "provider_id": "x",
                    "tool_id": "y",
                    "params": {},
                },
            ]
        )

        assert len(validate_tools) == 1
        assert validate_tools[0]["params"] == {"query": "hello"}
        assert tools[0]["tool"]["params"] == {"query": "hello"}

    def test_process_and_validate_datasets_should_filter_missing_and_keep_order(self):
        dataset_a = SimpleNamespace(
            id=uuid4(),
            name="知识库A",
            icon="a.png",
            description="A",
        )
        dataset_b = SimpleNamespace(
            id=uuid4(),
            name="知识库B",
            icon="b.png",
            description="B",
        )
        session = SimpleNamespace(query=lambda model: _QueryStub(all_result=[dataset_b, dataset_a]) if model is Dataset else _QueryStub())
        service = self._build_service(session=session)
        origin_ids = [str(dataset_a.id), "missing", str(dataset_b.id)]

        datasets, validate_datasets = service._process_and_validate_datasets(origin_ids)

        assert validate_datasets == [str(dataset_a.id), str(dataset_b.id)]
        assert [item["id"] for item in datasets] == [str(dataset_a.id), str(dataset_b.id)]

    def test_process_and_validate_workflows_should_filter_missing_and_keep_order(self):
        workflow_a = SimpleNamespace(
            id=uuid4(),
            name="工作流A",
            icon="a.png",
            description="A",
            status=WorkflowStatus.PUBLISHED.value,
        )
        workflow_b = SimpleNamespace(
            id=uuid4(),
            name="工作流B",
            icon="b.png",
            description="B",
            status=WorkflowStatus.PUBLISHED.value,
        )
        session = SimpleNamespace(
            query=lambda model: _QueryStub(all_result=[workflow_b, workflow_a]) if model is Workflow else _QueryStub()
        )
        service = self._build_service(session=session)
        origin_ids = [str(workflow_a.id), "missing", str(workflow_b.id)]

        workflows, validate_workflows = service._process_and_validate_workflows(origin_ids)

        assert validate_workflows == [str(workflow_a.id), str(workflow_b.id)]
        assert [item["id"] for item in workflows] == [str(workflow_a.id), str(workflow_b.id)]

    def test_process_and_validate_model_config_should_return_default_for_invalid_input_shapes(self):
        service = self._build_service()
        assert service._process_and_validate_model_config("invalid") == DEFAULT_APP_CONFIG["model_config"]
        assert service._process_and_validate_model_config({"provider": 123, "model": "gpt", "parameters": {}}) == DEFAULT_APP_CONFIG[
            "model_config"
        ]

        provider = SimpleNamespace(get_model_entity=lambda _model: None)
        service = self._build_service(language_model_manager=SimpleNamespace(get_provider=lambda _provider: provider))
        assert service._process_and_validate_model_config({"provider": "openai", "model": 123, "parameters": {}}) == DEFAULT_APP_CONFIG[
            "model_config"
        ]
        assert service._process_and_validate_model_config({"provider": "openai", "model": "missing", "parameters": {}}) == DEFAULT_APP_CONFIG[
            "model_config"
        ]

    def test_process_and_validate_model_config_should_fill_defaults_when_parameters_not_dict(self):
        params = [
            SimpleNamespace(name="temperature", default=0.7, required=False, type=SimpleNamespace(value="float"), options=[], min=0, max=1),
            SimpleNamespace(name="top_k", default=3, required=False, type=SimpleNamespace(value="int"), options=[], min=1, max=10),
        ]
        provider = SimpleNamespace(
            get_model_entity=lambda _model: SimpleNamespace(parameters=params)
        )
        service = self._build_service(language_model_manager=SimpleNamespace(get_provider=lambda _provider: provider))

        result = service._process_and_validate_model_config(
            {"provider": "openai", "model": "gpt-4o-mini", "parameters": ["bad"]}
        )

        assert result["parameters"] == {"temperature": 0.7, "top_k": 3}

    def test_process_and_validate_model_config_should_apply_required_optional_and_numeric_constraints(self):
        class _ParamType:
            def __init__(self, value):
                self.value = value

            def __eq__(self, other):
                return self.value == other

        params = [
            SimpleNamespace(
                name="role",
                default="assistant",
                required=True,
                type=_ParamType("string"),
                options=[],
                min=None,
                max=None,
            ),
            SimpleNamespace(
                name="top_k",
                default=2,
                required=False,
                type=_ParamType("int"),
                options=[],
                min=1,
                max=5,
            ),
            SimpleNamespace(
                name="mode",
                default="safe",
                required=False,
                type=_ParamType("string"),
                options=["safe", "fast"],
                min=None,
                max=None,
            ),
            SimpleNamespace(
                name="ratio",
                default=0.5,
                required=False,
                type=_ParamType("float"),
                options=[],
                min=0.1,
                max=0.9,
            ),
        ]
        provider = SimpleNamespace(get_model_entity=lambda _model: SimpleNamespace(parameters=params))
        service = self._build_service(
            language_model_manager=SimpleNamespace(get_provider=lambda _provider: provider)
        )

        result = service._process_and_validate_model_config(
            {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "parameters": {
                    "role": None,
                    "top_k": 0,
                    "mode": 123,
                    "ratio": 1.5,
                },
            }
        )

        assert result["parameters"]["role"] == "assistant"
        assert result["parameters"]["top_k"] == 2
        assert result["parameters"]["mode"] == "safe"
        assert result["parameters"]["ratio"] == 0.5

    def test_process_and_validate_model_config_should_keep_valid_values_without_fallback(self):
        class _ParamType:
            def __init__(self, value):
                self.value = value

            def __eq__(self, other):
                return self.value == other

        params = [
            SimpleNamespace(
                name="req_int",
                default=3,
                required=True,
                type=_ParamType("int"),
                options=[],
                min=1,
                max=10,
            ),
            SimpleNamespace(
                name="optional_text",
                default="default",
                required=False,
                type=_ParamType("string"),
                options=[],
                min=None,
                max=None,
            ),
        ]
        provider = SimpleNamespace(get_model_entity=lambda _model: SimpleNamespace(parameters=params))
        service = self._build_service(
            language_model_manager=SimpleNamespace(get_provider=lambda _provider: provider)
        )

        result = service._process_and_validate_model_config(
            {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "parameters": {"req_int": 6, "optional_text": None},
            }
        )

        assert result["parameters"]["req_int"] == 6
        assert result["parameters"]["optional_text"] is None
