from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from flask import Flask

from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import InvokeFrom
from internal.entity.platform_entity import WechatConfigStatus
from internal.model import account as account_model
from internal.model import api_key as api_key_model
from internal.model import api_tool as api_tool_model
from internal.model import app as app_model
from internal.model import conversation as conversation_model
from internal.model import dataset as dataset_model
from internal.model import platform as platform_model


class _QueryStub:
    def __init__(self, *, get_result=None, one_or_none_result=None, all_result=None, scalar_result=None):
        self._get_result = get_result
        self._one_or_none_result = one_or_none_result
        self._all_result = [] if all_result is None else all_result
        self._scalar_result = scalar_result

    def filter(self, *_args, **_kwargs):
        return self

    def filter_by(self, **_kwargs):
        return self

    def one_or_none(self):
        return self._one_or_none_result

    def all(self):
        return self._all_result

    def scalar(self):
        return self._scalar_result

    def get(self, *_args, **_kwargs):
        return self._get_result


class _SessionStub:
    def __init__(self, queries=None):
        self._queries = list(queries or [])
        self.added = []
        self.commits = 0
        self.flushes = 0

    def query(self, *_args, **_kwargs):
        if self._queries:
            return self._queries.pop(0)
        return _QueryStub()

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def flush(self):
        self.flushes += 1


@contextmanager
def _auto_commit():
    yield


def _fake_db(session):
    return SimpleNamespace(session=session, auto_commit=lambda: _auto_commit())


class TestAccountModel:
    def test_is_password_set_should_reflect_password_value(self):
        assert account_model.Account(password="abc").is_password_set is True
        assert account_model.Account(password="").is_password_set is False
        assert account_model.Account(password=None).is_password_set is False

    def test_assistant_agent_conversation_should_return_existing_record(self, monkeypatch):
        account_id = uuid4()
        existing = SimpleNamespace(
            id=uuid4(),
            is_deleted=False,
            created_by=account_id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        session = _SessionStub([_QueryStub(get_result=existing)])
        monkeypatch.setattr(account_model, "db", _fake_db(session))
        account = account_model.Account(id=account_id, assistant_agent_conversation_id=uuid4())
        flask_app = Flask(__name__)
        flask_app.config["ASSISTANT_AGENT_ID"] = str(uuid4())

        with flask_app.app_context():
            result = account.assistant_agent_conversation

        assert result is existing
        assert session.added == []

    def test_assistant_agent_conversation_should_create_when_missing(self, monkeypatch):
        class _Conversation:
            def __init__(self, **kwargs):
                self.id = uuid4()
                self.__dict__.update(kwargs)

        session = _SessionStub()
        monkeypatch.setattr(account_model, "db", _fake_db(session))
        monkeypatch.setattr(account_model, "Conversation", _Conversation)
        account = account_model.Account(id=uuid4(), assistant_agent_conversation_id=None)
        flask_app = Flask(__name__)
        flask_app.config["ASSISTANT_AGENT_ID"] = str(uuid4())

        with flask_app.app_context():
            result = account.assistant_agent_conversation

        assert isinstance(result, _Conversation)
        assert session.added == [result]
        assert account.assistant_agent_conversation_id == result.id


class TestAppModel:
    def test_utcnow_naive_helpers_should_return_naive_datetime(self):
        app_now = app_model._utcnow_naive()
        platform_now = platform_model._utcnow_naive()

        assert app_now.tzinfo is None
        assert platform_now.tzinfo is None

    def test_app_config_should_cover_none_and_query_branches(self, monkeypatch):
        app = app_model.App(id=uuid4(), account_id=uuid4())
        app.app_config_id = None
        assert app.app_config is None

        expected = SimpleNamespace(id=uuid4())
        session = _SessionStub([_QueryStub(get_result=expected)])
        monkeypatch.setattr(app_model, "db", _fake_db(session))
        app.app_config_id = uuid4()
        assert app.app_config is expected

    def test_draft_app_config_should_cover_existing_and_create_branches(self, monkeypatch):
        app = app_model.App(id=uuid4(), account_id=uuid4())
        existing = SimpleNamespace(id=uuid4())
        session_existing = _SessionStub([_QueryStub(one_or_none_result=existing)])
        monkeypatch.setattr(app_model, "db", _fake_db(session_existing))
        assert app.draft_app_config is existing

        session_missing = _SessionStub([_QueryStub(one_or_none_result=None)])
        monkeypatch.setattr(app_model, "db", _fake_db(session_missing))
        created = app.draft_app_config
        assert isinstance(created, app_model.AppConfigVersion)
        assert len(session_missing.added) == 1
        assert session_missing.commits == 1

    def test_debug_conversation_should_cover_existing_and_create_branches(self, monkeypatch):
        app = app_model.App(id=uuid4(), account_id=uuid4())
        existing = SimpleNamespace(id=uuid4())
        session_existing = _SessionStub([_QueryStub(one_or_none_result=existing)])
        monkeypatch.setattr(app_model, "db", _fake_db(session_existing))
        app.debug_conversation_id = uuid4()
        assert app.debug_conversation is existing

        class _Conversation:
            def __init__(self, **kwargs):
                self.id = uuid4()
                self.__dict__.update(kwargs)

        session_missing = _SessionStub()
        monkeypatch.setattr(app_model, "db", _fake_db(session_missing))
        monkeypatch.setattr(app_model, "Conversation", _Conversation)
        app.debug_conversation_id = None
        created = app.debug_conversation
        assert isinstance(created, _Conversation)
        assert session_missing.added == [created]
        assert session_missing.flushes == 1
        assert app.debug_conversation_id == created.id

    def test_token_with_default_should_cover_draft_and_published_branches(self, monkeypatch):
        session = _SessionStub()
        monkeypatch.setattr(app_model, "db", _fake_db(session))
        monkeypatch.setattr(app_model, "generate_random_string", lambda _n: "generated-token")

        app_draft = app_model.App(status=AppStatus.DRAFT.value, token="old")
        assert app_draft.token_with_default == ""
        assert app_draft.token is None
        assert session.commits >= 1

        before_none_branch = session.commits
        app_draft_none = app_model.App(status=AppStatus.DRAFT.value, token=None)
        assert app_draft_none.token_with_default == ""
        assert session.commits == before_none_branch

        app_published_empty = app_model.App(status=AppStatus.PUBLISHED.value, token="")
        assert app_published_empty.token_with_default == "generated-token"
        assert app_published_empty.token == "generated-token"

        before_commits = session.commits
        app_published_existing = app_model.App(status=AppStatus.PUBLISHED.value, token="kept")
        assert app_published_existing.token_with_default == "kept"
        assert session.commits == before_commits

    def test_wechat_config_should_cover_state_transitions(self, monkeypatch):
        app = app_model.App(id=uuid4(), status=AppStatus.DRAFT.value)

        session_create = _SessionStub([_QueryStub(one_or_none_result=None)])
        monkeypatch.setattr(app_model, "db", _fake_db(session_create))
        created = app.wechat_config
        assert created.status == WechatConfigStatus.UNCONFIGURED
        assert len(session_create.added) == 1
        assert session_create.commits == 1

        config_missing_field = SimpleNamespace(
            status=WechatConfigStatus.CONFIGURED,
            wechat_app_id="",
            wechat_app_secret="s",
            wechat_token="t",
        )
        session_missing_field = _SessionStub([_QueryStub(one_or_none_result=config_missing_field)])
        monkeypatch.setattr(app_model, "db", _fake_db(session_missing_field))
        app.status = AppStatus.PUBLISHED.value
        app.wechat_config
        assert config_missing_field.status == WechatConfigStatus.UNCONFIGURED
        assert session_missing_field.commits == 1

        config_draft = SimpleNamespace(
            status=WechatConfigStatus.CONFIGURED,
            wechat_app_id="a",
            wechat_app_secret="b",
            wechat_token="c",
        )
        session_draft = _SessionStub([_QueryStub(one_or_none_result=config_draft)])
        monkeypatch.setattr(app_model, "db", _fake_db(session_draft))
        app.status = AppStatus.DRAFT.value
        app.wechat_config
        assert config_draft.status == WechatConfigStatus.UNCONFIGURED
        assert session_draft.commits == 1

        config_publish = SimpleNamespace(
            status=WechatConfigStatus.UNCONFIGURED,
            wechat_app_id="a",
            wechat_app_secret="b",
            wechat_token="c",
        )
        session_publish = _SessionStub([_QueryStub(one_or_none_result=config_publish)])
        monkeypatch.setattr(app_model, "db", _fake_db(session_publish))
        app.status = AppStatus.PUBLISHED.value
        app.wechat_config
        assert config_publish.status == WechatConfigStatus.CONFIGURED
        assert session_publish.commits == 1

        config_published_no_change = SimpleNamespace(
            status=WechatConfigStatus.CONFIGURED,
            wechat_app_id="a",
            wechat_app_secret="b",
            wechat_token="c",
        )
        session_published_no_change = _SessionStub([_QueryStub(one_or_none_result=config_published_no_change)])
        monkeypatch.setattr(app_model, "db", _fake_db(session_published_no_change))
        app.status = AppStatus.PUBLISHED.value
        app.wechat_config
        assert config_published_no_change.status == WechatConfigStatus.CONFIGURED
        assert session_published_no_change.commits == 0

        config_unknown_status = SimpleNamespace(
            status=WechatConfigStatus.UNCONFIGURED,
            wechat_app_id="",
            wechat_app_secret="",
            wechat_token="",
        )
        session_unknown_status = _SessionStub([_QueryStub(one_or_none_result=config_unknown_status)])
        monkeypatch.setattr(app_model, "db", _fake_db(session_unknown_status))
        app.status = "unknown"
        app.wechat_config
        assert config_unknown_status.status == WechatConfigStatus.UNCONFIGURED
        assert session_unknown_status.commits == 0

    def test_app_config_dataset_joins_should_delegate_query(self, monkeypatch):
        joins = [SimpleNamespace(id=uuid4())]
        session = _SessionStub([_QueryStub(all_result=joins)])
        monkeypatch.setattr(app_model, "db", _fake_db(session))
        config = app_model.AppConfig(app_id=uuid4())

        assert config.app_dataset_joins == joins


class TestPlatformDatasetConversationAndApiModels:
    def test_wechat_end_user_conversation_should_cover_existing_and_create(self, monkeypatch):
        end_user = platform_model.WechatEndUser(app_id=uuid4(), end_user_id=uuid4())
        existing = SimpleNamespace(id=uuid4())
        session_existing = _SessionStub([_QueryStub(one_or_none_result=existing)])
        monkeypatch.setattr(platform_model, "db", _fake_db(session_existing))
        assert end_user.conversation is existing

        session_missing = _SessionStub([_QueryStub(one_or_none_result=None)])
        monkeypatch.setattr(platform_model, "db", _fake_db(session_missing))
        created = end_user.conversation
        assert isinstance(created, platform_model.Conversation)
        assert session_missing.added == [created]

    def test_dataset_document_and_segment_properties_should_delegate_queries(self, monkeypatch):
        dataset_id = uuid4()
        document = dataset_model.Document(id=uuid4(), dataset_id=dataset_id, upload_file_id=uuid4(), process_rule_id=uuid4())
        segment = dataset_model.Segment(document_id=document.id)
        upload_file = SimpleNamespace(id=document.upload_file_id)
        process_rule = SimpleNamespace(id=document.process_rule_id)
        session = _SessionStub(
            [
                _QueryStub(scalar_result=3),
                _QueryStub(scalar_result=5),
                _QueryStub(scalar_result=7),
                _QueryStub(scalar_result=9),
                _QueryStub(one_or_none_result=upload_file),
                _QueryStub(one_or_none_result=process_rule),
                _QueryStub(scalar_result=11),
                _QueryStub(scalar_result=13),
                _QueryStub(get_result=document),
            ]
        )
        monkeypatch.setattr(dataset_model, "db", _fake_db(session))
        dataset = dataset_model.Dataset(id=dataset_id)

        assert dataset.document_count == 3
        assert dataset.hit_count == 5
        assert dataset.related_app_count == 7
        assert dataset.character_count == 9
        assert document.upload_file is upload_file
        assert document.process_rule is process_rule
        assert document.segment_count == 11
        assert document.hit_count == 13
        assert segment.document is document

    def test_conversation_message_and_api_properties_should_delegate_queries(self, monkeypatch):
        conv = conversation_model.Conversation(id=uuid4())
        msg = conversation_model.Message(conversation_id=conv.id)
        account = SimpleNamespace(id=uuid4())
        provider = api_tool_model.ApiToolProvider(id=uuid4())
        tool = api_tool_model.ApiTool(provider_id=provider.id)
        session_conv = _SessionStub(
            [
                _QueryStub(scalar_result=1),
                _QueryStub(scalar_result=2),
                _QueryStub(get_result=conv),
            ]
        )
        monkeypatch.setattr(conversation_model, "db", _fake_db(session_conv))
        assert conv.is_new is True
        assert conversation_model.Conversation(id=uuid4()).is_new is False
        assert msg.conversation is conv

        session_api_key = _SessionStub([_QueryStub(get_result=account)])
        monkeypatch.setattr(api_key_model, "db", _fake_db(session_api_key))
        assert api_key_model.ApiKey(account_id=uuid4()).account is account

        session_api_tool = _SessionStub(
            [
                _QueryStub(all_result=[tool]),
                _QueryStub(get_result=provider),
            ]
        )
        monkeypatch.setattr(api_tool_model, "db", _fake_db(session_api_tool))
        assert provider.tools == [tool]
        assert tool.provider is provider
