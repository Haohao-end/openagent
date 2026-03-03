from contextlib import contextmanager
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Flask
from wechatpy.exceptions import InvalidSignatureException

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import MessageStatus
from internal.entity.platform_entity import WechatConfigStatus
from internal.exception import FailException
from internal.model import Message, WechatEndUser, WechatMessage
from internal.service.wechat_service import WechatService


class _DummyTextReply:
    def __init__(self, content, message):
        self.content = content
        self.message = message

    def render(self):
        return self.content


def _message(msg_type="text", content="hello", target="openid-1"):
    return SimpleNamespace(type=msg_type, content=content, target=target)


def _build_service():
    return WechatService(
        db=SimpleNamespace(session=SimpleNamespace()),
        retrieval_service=SimpleNamespace(),
        app_config_service=SimpleNamespace(),
        conversation_service=SimpleNamespace(),
        language_model_service=SimpleNamespace(),
    )


class _DummyQuery:
    def __init__(self, one_or_none_result=None, first_result=None):
        self._one_or_none_result = one_or_none_result
        self._first_result = first_result

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def one_or_none(self):
        return self._one_or_none_result

    def first(self):
        return self._first_result


class _DummySession:
    def __init__(self, query_by_model_name):
        self.query_by_model_name = query_by_model_name

    def query(self, model):
        model_name = model.__name__
        if model_name not in self.query_by_model_name:
            raise AssertionError(f"unexpected query model: {model_name}")
        return self.query_by_model_name[model_name]


class TestWechatService:
    def test_wechat_should_raise_for_get_when_app_not_published(self, monkeypatch):
        service = _build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)
        monkeypatch.setattr("internal.service.wechat_service.parse_message", lambda _data: _message())
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(
            f"/wechat/{uuid4()}?signature=s&timestamp=t&nonce=n&echostr=ok",
            method="GET",
        ):
            with pytest.raises(FailException):
                service.wechat(uuid4())

    def test_wechat_should_return_text_for_post_when_app_not_published(self, monkeypatch):
        service = _build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)
        monkeypatch.setattr("internal.service.wechat_service.parse_message", lambda _data: _message())
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{uuid4()}", method="POST", data=b"<xml/>"):
            result = service.wechat(uuid4())

        assert "未发布或不存在" in result

    def test_wechat_should_raise_for_get_when_config_is_not_ready(self, monkeypatch):
        app = SimpleNamespace(
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(
                status=WechatConfigStatus.UNCONFIGURED,
                wechat_token="token",
            ),
        )
        service = _build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)
        monkeypatch.setattr("internal.service.wechat_service.parse_message", lambda _data: _message())
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(
            f"/wechat/{uuid4()}?signature=s&timestamp=t&nonce=n&echostr=ok",
            method="GET",
        ):
            with pytest.raises(FailException):
                service.wechat(uuid4())

    def test_wechat_should_return_echostr_when_signature_valid(self, monkeypatch):
        app = SimpleNamespace(
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(
                status=WechatConfigStatus.CONFIGURED,
                wechat_token="token",
            ),
        )
        service = _build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)
        monkeypatch.setattr("internal.service.wechat_service.parse_message", lambda _data: _message())
        monkeypatch.setattr("internal.service.wechat_service.check_signature", lambda *_args, **_kwargs: None)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(
            f"/wechat/{uuid4()}?signature=s&timestamp=t&nonce=n&echostr=ok",
            method="GET",
        ):
            result = service.wechat(uuid4())

        assert result == "ok"

    def test_wechat_should_raise_when_signature_invalid(self, monkeypatch):
        app = SimpleNamespace(
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(
                status=WechatConfigStatus.CONFIGURED,
                wechat_token="token",
            ),
        )
        service = _build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)
        monkeypatch.setattr("internal.service.wechat_service.parse_message", lambda _data: _message())
        monkeypatch.setattr(
            "internal.service.wechat_service.check_signature",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(InvalidSignatureException()),
        )

        flask_app = Flask(__name__)
        with flask_app.test_request_context(
            f"/wechat/{uuid4()}?signature=s&timestamp=t&nonce=n&echostr=ok",
            method="GET",
        ):
            with pytest.raises(FailException):
                service.wechat(uuid4())

    def test_wechat_should_reject_non_text_messages_on_post(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(
                status=WechatConfigStatus.CONFIGURED,
                wechat_token="token",
            ),
        )
        service = _build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(msg_type="image"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{uuid4()}", method="POST", data=b"<xml/>"):
            result = service.wechat(uuid4())

        assert "只支持文本消息" in result

    def test_wechat_should_return_text_for_post_when_config_is_not_ready(self, monkeypatch):
        app = SimpleNamespace(
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(
                status=WechatConfigStatus.UNCONFIGURED,
                wechat_token="token",
            ),
        )
        service = _build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)
        monkeypatch.setattr("internal.service.wechat_service.parse_message", lambda _data: _message())
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{uuid4()}", method="POST", data=b"<xml/>"):
            result = service.wechat(uuid4())

        assert "未发布到微信公众号" in result

    def test_wechat_should_push_message_answer_when_user_replies_one(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        wechat_message = SimpleNamespace(id=uuid4(), message_id=uuid4(), is_pushed=False)
        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                    "WechatMessage": _DummyQuery(first_result=wechat_message),
                }
            )
        )

        message = SimpleNamespace(status=MessageStatus.NORMAL, answer="  这是答案  ", error="")

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model is Message:
                return message
            return None

        monkeypatch.setattr(service, "get", _get)
        updates = []
        monkeypatch.setattr(service, "update", lambda target, **kwargs: updates.append((target, kwargs)))
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="1", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            result = service.wechat(app.id)

        assert result == "这是答案"
        assert updates == [(wechat_message, {"is_pushed": True})]

    @pytest.mark.parametrize(
        "status,error,expected",
        [
            (MessageStatus.TIMEOUT, "", "任务超时"),
            (MessageStatus.ERROR, "boom", "错误信息: boom"),
        ],
    )
    def test_wechat_should_return_status_hint_when_user_replies_one(self, status, error, expected, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        wechat_message = SimpleNamespace(id=uuid4(), message_id=uuid4(), is_pushed=False)
        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                    "WechatMessage": _DummyQuery(first_result=wechat_message),
                }
            )
        )

        message = SimpleNamespace(status=status, answer="", error=error)

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model is Message:
                return message
            return None

        monkeypatch.setattr(service, "get", _get)
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="1", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            result = service.wechat(app.id)

        assert expected in result

    def test_wechat_should_return_pending_hint_when_answer_not_ready(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        wechat_message = SimpleNamespace(id=uuid4(), message_id=uuid4(), is_pushed=False)
        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                    "WechatMessage": _DummyQuery(first_result=wechat_message),
                }
            )
        )
        message = SimpleNamespace(status=MessageStatus.NORMAL, answer="   ", error="")

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model is Message:
                return message
            return None

        monkeypatch.setattr(service, "get", _get)
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="1", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            result = service.wechat(app.id)

        assert "任务正在处理中" in result

    def test_wechat_should_treat_reply_one_as_normal_input_when_wechat_message_missing(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                    "WechatMessage": _DummyQuery(first_result=None),
                }
            )
        )
        monkeypatch.setattr(service, "get", lambda model, _id: app if model.__name__ == "App" else None)
        created_message = SimpleNamespace(id=uuid4())
        created = []

        def _create(model, **kwargs):
            created.append((model, kwargs))
            if model is Message:
                return created_message
            if model is WechatMessage:
                return SimpleNamespace(id=uuid4())
            raise AssertionError(f"unexpected model: {model}")

        monkeypatch.setattr(service, "create", _create)
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: {
                "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
                "dialog_round": 2,
                "tools": [],
                "datasets": [],
                "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.6},
                "workflows": [],
                "preset_prompt": "preset",
                "long_term_memory": {"enable": False},
                "review_config": {"enable": False},
            }
        )

        class _FakeThread:
            def __init__(self, target, kwargs):
                self.target = target
                self.kwargs = kwargs

            def start(self):
                return None

        monkeypatch.setattr("internal.service.wechat_service.Thread", _FakeThread)
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="1", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            result = service.wechat(app.id)

        assert "思考中，请回复“1”获取结果" in result
        assert created[0][0] is Message
        assert created[1][0] is WechatMessage

    def test_wechat_should_treat_reply_one_as_normal_input_when_agent_message_missing(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        wechat_message = SimpleNamespace(id=uuid4(), message_id=uuid4(), is_pushed=False)
        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                    "WechatMessage": _DummyQuery(first_result=wechat_message),
                }
            )
        )

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model is Message:
                return None
            return None

        monkeypatch.setattr(service, "get", _get)
        created = []
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: created.append((model, kwargs)) or SimpleNamespace(id=uuid4()),
        )
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: {
                "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
                "dialog_round": 2,
                "tools": [],
                "datasets": [],
                "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.6},
                "workflows": [],
                "preset_prompt": "preset",
                "long_term_memory": {"enable": False},
                "review_config": {"enable": False},
            }
        )
        monkeypatch.setattr(
            "internal.service.wechat_service.Thread",
            lambda target, kwargs: SimpleNamespace(start=lambda: None, target=target, kwargs=kwargs),
        )
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="1", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            result = service.wechat(app.id)

        assert "思考中，请回复“1”获取结果" in result
        assert created[0][0] is Message

    def test_wechat_should_return_empty_content_when_message_status_unknown(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        wechat_message = SimpleNamespace(id=uuid4(), message_id=uuid4(), is_pushed=False)
        message = SimpleNamespace(status="unknown-status", answer="", error="")
        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                    "WechatMessage": _DummyQuery(first_result=wechat_message),
                }
            )
        )

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model is Message:
                return message
            return None

        monkeypatch.setattr(service, "get", _get)
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="1", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            result = service.wechat(app.id)

        assert result == ""

    def test_wechat_should_create_end_user_and_wechat_end_user_when_first_contact(self, monkeypatch):
        class _CreateSession:
            def __init__(self):
                self.added = []
                self.queries = {"WechatEndUser": _DummyQuery(one_or_none_result=None)}

            def query(self, model):
                model_name = model.__name__
                if model_name in self.queries:
                    return self.queries[model_name]
                if model_name.endswith("WechatEndUser"):
                    return self.queries["WechatEndUser"]
                raise AssertionError(f"unexpected query model: {model_name}")

            def add(self, obj):
                self.added.append(obj)

            def flush(self):
                if self.added and getattr(self.added[-1], "id", None) is None:
                    self.added[-1].id = uuid4()

        class _CreateDB:
            def __init__(self):
                self.session = _CreateSession()
                self.auto_commit_count = 0

            @contextmanager
            def auto_commit(self):
                self.auto_commit_count += 1
                yield

        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")

        class _FakeEndUser:
            def __init__(self, tenant_id, app_id):
                self.tenant_id = tenant_id
                self.app_id = app_id
                self.id = None

        class _FakeWechatEndUser:
            openid = ""
            app_id = ""

            def __init__(self, openid, app_id, end_user_id):
                self.id = uuid4()
                self.openid = openid
                self.app_id = app_id
                self.end_user_id = end_user_id
                self.conversation = conversation

        service = _build_service()
        service.db = _CreateDB()
        monkeypatch.setattr("internal.service.wechat_service.EndUser", _FakeEndUser)
        monkeypatch.setattr("internal.service.wechat_service.WechatEndUser", _FakeWechatEndUser)
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: app if model.__name__ == "App" else None,
        )
        created = []
        created_message = SimpleNamespace(id=uuid4())

        def _create(model, **kwargs):
            created.append((model, kwargs))
            if model is Message:
                return created_message
            if model is WechatMessage:
                return SimpleNamespace(id=uuid4())
            raise AssertionError(f"unexpected model: {model}")

        monkeypatch.setattr(service, "create", _create)
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: {
                "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
                "dialog_round": 2,
                "tools": [],
                "datasets": [],
                "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.6},
                "workflows": [],
                "preset_prompt": "preset",
                "long_term_memory": {"enable": False},
                "review_config": {"enable": False},
            }
        )

        class _FakeThread:
            def __init__(self, target, kwargs):
                self.target = target
                self.kwargs = kwargs

            def start(self):
                return None

        monkeypatch.setattr("internal.service.wechat_service.Thread", _FakeThread)
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="你好", target="openid-new"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            result = service.wechat(app.id)

        assert "思考中，请回复“1”获取结果" in result
        assert service.db.auto_commit_count == 1
        assert len(service.db.session.added) == 2
        assert isinstance(service.db.session.added[0], _FakeEndUser)
        assert isinstance(service.db.session.added[1], _FakeWechatEndUser)
        assert service.db.session.added[1].openid == "openid-new"
        assert created[0][0] is Message
        assert created[1][0] is WechatMessage

    def test_wechat_should_create_message_and_start_thread_for_normal_text(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                }
            )
        )

        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: app if model.__name__ == "App" else None,
        )
        created = []
        created_message = SimpleNamespace(id=uuid4())

        def _create(model, **kwargs):
            created.append((model, kwargs))
            if model is Message:
                return created_message
            if model is WechatMessage:
                return SimpleNamespace(id=uuid4())
            raise AssertionError(f"unexpected model: {model}")

        monkeypatch.setattr(service, "create", _create)
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: {
                "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
                "dialog_round": 2,
                "tools": [],
                "datasets": [],
                "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.6},
                "workflows": [],
                "preset_prompt": "preset",
                "long_term_memory": {"enable": False},
                "review_config": {"enable": False},
            }
        )
        thread_capture = {}

        class _FakeThread:
            def __init__(self, target, kwargs):
                thread_capture["target"] = target
                thread_capture["kwargs"] = kwargs
                thread_capture["started"] = False

            def start(self):
                thread_capture["started"] = True

        monkeypatch.setattr("internal.service.wechat_service.Thread", _FakeThread)
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="你好", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            result = service.wechat(app.id)

        assert "思考中，请回复“1”获取结果" in result
        assert created[0][0] is Message
        assert created[1][0] is WechatMessage
        assert thread_capture["started"] is True
        assert thread_capture["kwargs"]["app_id"] == app.id
        assert thread_capture["kwargs"]["conversation_id"] == conversation.id
        assert thread_capture["kwargs"]["message_id"] == created_message.id
        assert thread_capture["kwargs"]["query"] == "你好"

    def test_thread_chat_should_build_tools_and_persist_agent_thoughts(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(id=uuid4(), account_id=uuid4())
        conversation = SimpleNamespace(id=uuid4(), summary="history-summary")

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model.__name__ == "Conversation":
                return conversation
            return None

        monkeypatch.setattr(service, "get", _get)
        llm = SimpleNamespace(
            features=[ModelFeature.TOOL_CALL],
            convert_to_human_message=lambda query, image_urls: f"{query}:{len(image_urls)}",
        )
        service.language_model_service = SimpleNamespace(load_language_model=lambda _model_config: llm)

        class _FakeTokenBufferMemory:
            def __init__(self, **_kwargs):
                pass

            def get_history_prompt_messages(self, message_limit):
                assert message_limit == 2
                return ["history"]

        monkeypatch.setattr("internal.service.wechat_service.TokenBufferMemory", _FakeTokenBufferMemory)

        service.app_config_service = SimpleNamespace(
            get_langchain_tools_by_tools_config=lambda _tools: ["builtin-tool"],
            get_langchain_tools_by_workflow_ids=lambda _workflow_ids: ["workflow-tool"],
        )
        retrieval_capture = {}
        service.retrieval_service = SimpleNamespace(
            create_langchain_tool_from_search=lambda **kwargs: retrieval_capture.update(kwargs) or "dataset-tool"
        )
        captured_tools = {}

        class _FakeFunctionCallAgent:
            def __init__(self, llm, agent_config):
                captured_tools["tools"] = agent_config.tools

            def invoke(self, _agent_state):
                return SimpleNamespace(
                    agent_thoughts=[
                        AgentThought(
                            id=uuid4(),
                            task_id=uuid4(),
                            event=QueueEvent.AGENT_END,
                            answer="done",
                        )
                    ]
                )

        # tools 字段在 AgentConfig 中是 BaseTool 类型，单测里用简单对象替代以隔离第三方依赖。
        monkeypatch.setattr(
            "internal.service.wechat_service.AgentConfig",
            lambda **kwargs: SimpleNamespace(**kwargs),
        )
        monkeypatch.setattr("internal.service.wechat_service.FunctionCallAgent", _FakeFunctionCallAgent)
        save_payload = {}
        service.conversation_service = SimpleNamespace(
            save_agent_thoughts=lambda **kwargs: save_payload.update(kwargs)
        )

        app_config = {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "dialog_round": 2,
            "tools": [{"type": "builtin_tool"}],
            "datasets": [{"id": "dataset-1"}],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.5},
            "workflows": [{"id": "workflow-1"}],
            "preset_prompt": "preset",
            "long_term_memory": {"enable": True},
            "review_config": {"enable": False},
        }
        flask_app = Flask(__name__)
        flask_proxy = SimpleNamespace(
            app_context=flask_app.app_context,
            _get_current_object=lambda: flask_app,
        )

        service._thread_chat(
            flask_app=flask_proxy,
            app_id=app.id,
            app_config=app_config,
            message_id=uuid4(),
            conversation_id=conversation.id,
            query="hello",
        )

        assert len(captured_tools["tools"]) == 3
        assert retrieval_capture["dataset_ids"] == ["dataset-1"]
        assert retrieval_capture["account_id"] == app.account_id
        assert "retrival_source" in retrieval_capture
        assert save_payload["conversation_id"] == conversation.id
        assert len(save_payload["agent_thoughts"]) == 1

    def test_thread_chat_should_skip_dataset_and_workflow_tools_when_not_configured(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(id=uuid4(), account_id=uuid4())
        conversation = SimpleNamespace(id=uuid4(), summary="history-summary")

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model.__name__ == "Conversation":
                return conversation
            return None

        monkeypatch.setattr(service, "get", _get)
        llm = SimpleNamespace(
            features=[ModelFeature.TOOL_CALL],
            convert_to_human_message=lambda query, image_urls: f"{query}:{len(image_urls)}",
        )
        service.language_model_service = SimpleNamespace(load_language_model=lambda _model_config: llm)
        monkeypatch.setattr(
            "internal.service.wechat_service.TokenBufferMemory",
            lambda **_kwargs: SimpleNamespace(get_history_prompt_messages=lambda message_limit: []),
        )

        service.app_config_service = SimpleNamespace(
            get_langchain_tools_by_tools_config=lambda _tools: ["builtin-tool"],
            get_langchain_tools_by_workflow_ids=lambda _workflow_ids: (_ for _ in ()).throw(
                AssertionError("workflow tool builder should not be called")
            ),
        )
        service.retrieval_service = SimpleNamespace(
            create_langchain_tool_from_search=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("dataset retrieval tool builder should not be called")
            )
        )
        captured_tools = {}

        class _FakeFunctionCallAgent:
            def __init__(self, llm, agent_config):
                captured_tools["tools"] = agent_config.tools

            def invoke(self, _agent_state):
                return SimpleNamespace(agent_thoughts=[])

        monkeypatch.setattr(
            "internal.service.wechat_service.AgentConfig",
            lambda **kwargs: SimpleNamespace(**kwargs),
        )
        monkeypatch.setattr("internal.service.wechat_service.FunctionCallAgent", _FakeFunctionCallAgent)
        service.conversation_service = SimpleNamespace(save_agent_thoughts=lambda **_kwargs: None)

        app_config = {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "dialog_round": 2,
            "tools": [{"type": "builtin_tool"}],
            "datasets": [],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.5},
            "workflows": [],
            "preset_prompt": "preset",
            "long_term_memory": {"enable": True},
            "review_config": {"enable": False},
        }
        flask_app = Flask(__name__)
        flask_proxy = SimpleNamespace(
            app_context=flask_app.app_context,
            _get_current_object=lambda: flask_app,
        )

        service._thread_chat(
            flask_app=flask_proxy,
            app_id=app.id,
            app_config=app_config,
            message_id=uuid4(),
            conversation_id=conversation.id,
            query="hello",
        )

        assert captured_tools["tools"] == ["builtin-tool"]

    def test_wechat_should_be_idempotent_for_reentrant_pending_poll_requests(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        wechat_message = SimpleNamespace(id=uuid4(), message_id=uuid4(), is_pushed=False)
        message = SimpleNamespace(status=MessageStatus.NORMAL, answer="   ", error="")

        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                    "WechatMessage": _DummyQuery(first_result=wechat_message),
                }
            )
        )

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model is Message:
                return message
            return None

        created = []
        thread_starts = {"count": 0}
        monkeypatch.setattr(service, "get", _get)
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: created.append((model, kwargs)) or SimpleNamespace(id=uuid4()),
        )
        monkeypatch.setattr("internal.service.wechat_service.Thread", lambda *_args, **_kwargs: SimpleNamespace(
            start=lambda: thread_starts.__setitem__("count", thread_starts["count"] + 1)
        ))
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="1", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            first = service.wechat(app.id)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            second = service.wechat(app.id)

        assert "任务正在处理中" in first
        assert "任务正在处理中" in second
        assert created == []
        assert thread_starts["count"] == 0

    def test_wechat_should_create_new_task_after_result_has_been_pushed_once(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        wechat_message = SimpleNamespace(id=uuid4(), message_id=uuid4(), is_pushed=False)
        message = SimpleNamespace(status=MessageStatus.NORMAL, answer="已完成答案", error="")

        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                    "WechatMessage": _DummyQuery(first_result=wechat_message),
                }
            )
        )

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model is Message:
                return message
            return None

        updates = []
        created = []
        thread_starts = {"count": 0}
        created_message = SimpleNamespace(id=uuid4())

        def _update(target, **kwargs):
            updates.append((target, kwargs))
            for key, value in kwargs.items():
                setattr(target, key, value)

        def _create(model, **kwargs):
            created.append((model, kwargs))
            if model is Message:
                return created_message
            if model is WechatMessage:
                return SimpleNamespace(id=uuid4())
            raise AssertionError(f"unexpected model: {model}")

        monkeypatch.setattr(service, "get", _get)
        monkeypatch.setattr(service, "update", _update)
        monkeypatch.setattr(service, "create", _create)
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: {
                "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
                "dialog_round": 2,
                "tools": [],
                "datasets": [],
                "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.6},
                "workflows": [],
                "preset_prompt": "preset",
                "long_term_memory": {"enable": False},
                "review_config": {"enable": False},
            }
        )
        monkeypatch.setattr(
            "internal.service.wechat_service.Thread",
            lambda *_args, **_kwargs: SimpleNamespace(
                start=lambda: thread_starts.__setitem__("count", thread_starts["count"] + 1)
            ),
        )
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="1", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            first = service.wechat(app.id)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            second = service.wechat(app.id)

        assert first == "已完成答案"
        assert "思考中，请回复“1”获取结果" in second
        assert updates == [(wechat_message, {"is_pushed": True})]
        assert [model for model, _ in created] == [Message, WechatMessage]
        assert thread_starts["count"] == 1

    def test_wechat_should_handle_concurrent_normal_messages_from_same_openid(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                }
            )
        )
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: app if model.__name__ == "App" else None,
        )
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: {
                "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
                "dialog_round": 2,
                "tools": [],
                "datasets": [],
                "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.6},
                "workflows": [],
                "preset_prompt": "preset",
                "long_term_memory": {"enable": False},
                "review_config": {"enable": False},
            }
        )
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="并发提问", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        lock = threading.Lock()
        created = []
        thread_started = {"count": 0}
        sequence = {"value": 0}

        def _create(model, **kwargs):
            with lock:
                created.append((model, kwargs))
                if model is Message:
                    sequence["value"] += 1
                    return SimpleNamespace(id=f"message-{sequence['value']}")
                if model is WechatMessage:
                    sequence["value"] += 1
                    return SimpleNamespace(id=f"wechat-message-{sequence['value']}")
            raise AssertionError(f"unexpected model: {model}")

        service.create = _create

        def _start_inner_thread():
            with lock:
                thread_started["count"] += 1

        monkeypatch.setattr(
            "internal.service.wechat_service.Thread",
            lambda *_args, **_kwargs: SimpleNamespace(
                start=_start_inner_thread
            ),
        )

        flask_app = Flask(__name__)
        barrier = threading.Barrier(3)
        results = []

        def _invoke_once():
            with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
                barrier.wait()
                result = service.wechat(app.id)
            with lock:
                results.append(result)

        t1 = threading.Thread(target=_invoke_once)
        t2 = threading.Thread(target=_invoke_once)
        t1.start()
        t2.start()
        barrier.wait()
        t1.join()
        t2.join()

        assert len(results) == 2
        assert all("思考中，请回复“1”获取结果" in item for item in results)
        assert [model for model, _ in created].count(Message) == 2
        assert [model for model, _ in created].count(WechatMessage) == 2
        assert thread_started["count"] == 2

    def test_wechat_should_push_answer_after_pending_state_transitions_to_ready(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        wechat_message = SimpleNamespace(id=uuid4(), message_id=uuid4(), is_pushed=False)
        message = SimpleNamespace(status=MessageStatus.NORMAL, answer="  ", error="")

        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                    "WechatMessage": _DummyQuery(first_result=wechat_message),
                }
            )
        )

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model is Message:
                return message
            return None

        updates = []

        def _update(target, **kwargs):
            updates.append((target, kwargs))
            for key, value in kwargs.items():
                setattr(target, key, value)

        monkeypatch.setattr(service, "get", _get)
        monkeypatch.setattr(service, "update", _update)
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="1", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            pending_reply = service.wechat(app.id)

        message.answer = "  最终答案  "
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            final_reply = service.wechat(app.id)

        assert "任务正在处理中" in pending_reply
        assert final_reply == "最终答案"
        assert updates == [(wechat_message, {"is_pushed": True})]

    def test_wechat_should_keep_error_poll_idempotent_for_replayed_same_message(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        wechat_message = SimpleNamespace(id=uuid4(), message_id=uuid4(), is_pushed=False)
        message = SimpleNamespace(status=MessageStatus.ERROR, answer="", error="upstream timeout")

        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                    "WechatMessage": _DummyQuery(first_result=wechat_message),
                }
            )
        )

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model is Message:
                return message
            return None

        created = []
        updates = []
        thread_starts = {"count": 0}
        monkeypatch.setattr(service, "get", _get)
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: created.append((model, kwargs)) or SimpleNamespace(id=uuid4()),
        )
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )
        monkeypatch.setattr(
            "internal.service.wechat_service.Thread",
            lambda *_args, **_kwargs: SimpleNamespace(
                start=lambda: thread_starts.__setitem__("count", thread_starts["count"] + 1)
            ),
        )
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="1", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            first = service.wechat(app.id)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            second = service.wechat(app.id)

        assert "处理任务出错" in first
        assert second == first
        assert updates == []
        assert created == []
        assert thread_starts["count"] == 0

    def test_wechat_should_handle_out_of_order_error_then_ready_transition_for_same_poll(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED,
            wechat_config=SimpleNamespace(status=WechatConfigStatus.CONFIGURED, wechat_token="token"),
        )
        conversation = SimpleNamespace(id=uuid4(), summary="")
        wechat_end_user = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            end_user_id=uuid4(),
            conversation=conversation,
        )
        wechat_message = SimpleNamespace(id=uuid4(), message_id=uuid4(), is_pushed=False)
        message = SimpleNamespace(status=MessageStatus.ERROR, answer="", error="temporary error")

        service = _build_service()
        service.db = SimpleNamespace(
            session=_DummySession(
                {
                    "WechatEndUser": _DummyQuery(one_or_none_result=wechat_end_user),
                    "WechatMessage": _DummyQuery(first_result=wechat_message),
                }
            )
        )

        def _get(model, _id):
            if model.__name__ == "App":
                return app
            if model is Message:
                return message
            return None

        created = []
        updates = []
        thread_starts = {"count": 0}

        def _update(target, **kwargs):
            updates.append((target, kwargs))
            for key, value in kwargs.items():
                setattr(target, key, value)

        monkeypatch.setattr(service, "get", _get)
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: created.append((model, kwargs)) or SimpleNamespace(id=uuid4()),
        )
        monkeypatch.setattr(service, "update", _update)
        monkeypatch.setattr(
            "internal.service.wechat_service.Thread",
            lambda *_args, **_kwargs: SimpleNamespace(
                start=lambda: thread_starts.__setitem__("count", thread_starts["count"] + 1)
            ),
        )
        monkeypatch.setattr(
            "internal.service.wechat_service.parse_message",
            lambda _data: _message(content="1", target="openid-1"),
        )
        monkeypatch.setattr("internal.service.wechat_service.TextReply", _DummyTextReply)

        flask_app = Flask(__name__)
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            error_reply = service.wechat(app.id)

        message.status = MessageStatus.NORMAL
        message.answer = "  恢复后的最终答案  "
        message.error = ""
        with flask_app.test_request_context(f"/wechat/{app.id}", method="POST", data=b"<xml/>"):
            ready_reply = service.wechat(app.id)

        assert "处理任务出错" in error_reply
        assert ready_reply == "恢复后的最终答案"
        assert updates == [(wechat_message, {"is_pushed": True})]
        assert created == []
        assert thread_starts["count"] == 0
