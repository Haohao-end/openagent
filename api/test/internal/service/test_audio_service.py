from types import SimpleNamespace
from uuid import uuid4

import pytest
import requests
from io import BytesIO
from werkzeug.datastructures import FileStorage

from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import InvokeFrom
from internal.exception import FailException, NotFoundException
from internal.service.audio_service import AudioService


class _DummyResponse:
    def __init__(self, chunks=None, raise_error=False):
        self._chunks = chunks or []
        self._raise_error = raise_error
        self.closed = False

    def iter_content(self, chunk_size=1024):
        if self._raise_error:
            raise RuntimeError("stream failed")
        for chunk in self._chunks:
            yield chunk

    def close(self):
        self.closed = True


def _build_service():
    return AudioService(
        db=SimpleNamespace(),
        app_service=SimpleNamespace(),
    )


class TestAudioService:
    def test_validate_siliconflow_config_should_report_missing_keys(self, monkeypatch):
        monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
        monkeypatch.delenv("SILICONFLOW_API_BASE", raising=False)

        with pytest.raises(FailException) as exc_info:
            AudioService._validate_siliconflow_config()

        message = str(exc_info.value)
        assert "SILICONFLOW_API_KEY" in message
        assert "SILICONFLOW_API_BASE" in message

    def test_audio_to_text_should_call_asr_endpoint_and_trim_text(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")
        captured = {}

        class _Response:
            def raise_for_status(self):
                return None

            @staticmethod
            def json():
                return {"text": "  hello world  "}

        def _fake_post(url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return _Response()

        monkeypatch.setattr("internal.service.audio_service.requests.post", _fake_post)
        audio = FileStorage(stream=BytesIO(b"wav-data"), filename="voice.wav")

        text = service.audio_to_text(audio)

        assert text == "hello world"
        assert captured["url"] == "https://api.example.com/v1/audio/transcriptions"
        assert captured["kwargs"]["data"]["model"] == "TeleAI/TeleSpeechASR"
        assert captured["kwargs"]["timeout"] == 60

    def test_audio_to_text_should_raise_when_audio_is_empty(self):
        service = _build_service()
        audio = FileStorage(stream=BytesIO(b""), filename="empty.wav")

        with pytest.raises(FailException):
            service.audio_to_text(audio)

    def test_audio_to_text_should_raise_when_siliconflow_config_missing(self, monkeypatch):
        service = _build_service()
        monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
        monkeypatch.delenv("SILICONFLOW_API_BASE", raising=False)
        audio = FileStorage(stream=BytesIO(b"wav-data"), filename="voice.wav")

        with pytest.raises(FailException, match="语音服务配置缺失"):
            service.audio_to_text(audio)

    def test_audio_to_text_should_wrap_request_error(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")
        monkeypatch.setattr(
            "internal.service.audio_service.requests.post",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("network-error")),
        )
        audio = FileStorage(stream=BytesIO(b"wav-data"), filename="voice.wav")

        with pytest.raises(FailException):
            service.audio_to_text(audio)

    def test_text_to_audio_should_raise_when_text_is_empty(self):
        service = _build_service()

        with pytest.raises(FailException):
            service.text_to_audio(message_id=None, text="   ", account=SimpleNamespace(id=uuid4()))

    def test_get_valid_message_should_raise_when_message_id_is_invalid(self):
        service = _build_service()

        with pytest.raises(NotFoundException):
            service._get_valid_message(message_id="bad-uuid", account=SimpleNamespace(id=uuid4()))

    def test_message_to_audio_should_raise_when_answer_is_empty(self, monkeypatch):
        service = _build_service()
        message = SimpleNamespace(id=uuid4(), answer="   ")
        conversation = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "_get_valid_message", lambda *_args, **_kwargs: (message, conversation))

        with pytest.raises(NotFoundException):
            service.message_to_audio(uuid4(), SimpleNamespace(id=uuid4()))

    def test_message_to_audio_should_resolve_voice_then_stream(self, monkeypatch):
        service = _build_service()
        message = SimpleNamespace(id=uuid4(), answer="hello world")
        conversation = SimpleNamespace(id=uuid4())
        account = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "_get_valid_message", lambda *_args, **_kwargs: (message, conversation))
        monkeypatch.setattr(service, "_resolve_voice", lambda *_args, **_kwargs: "anna")
        captures = {}
        monkeypatch.setattr(
            service,
            "_create_tts_response",
            lambda input_text, voice: captures.update({"input_text": input_text, "voice": voice}) or "resp",
        )
        monkeypatch.setattr(
            service,
            "_stream_tts_response",
            lambda response, common_data: iter([f"{response}:{common_data['conversation_id']}:{common_data['message_id']}"]),
        )

        events = list(service.message_to_audio(message.id, account))

        assert captures["input_text"] == "hello world"
        assert captures["voice"] == "anna"
        assert events == [f"resp:{conversation.id}:{message.id}"]

    def test_text_to_audio_should_use_default_context_when_message_id_missing(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        captures = {}
        monkeypatch.setattr(
            service,
            "_create_tts_response",
            lambda input_text, voice: captures.update({"input_text": input_text, "voice": voice}) or "resp",
        )
        monkeypatch.setattr(
            service,
            "_stream_tts_response",
            lambda response, common_data: iter([f"{response}:{common_data['conversation_id']}:{common_data['message_id']}"]),
        )

        events = list(service.text_to_audio(message_id=None, text="  播放这段文字  ", account=account))

        assert captures["input_text"] == "播放这段文字"
        assert captures["voice"] == "alex"
        assert events == ["resp::"]

    def test_text_to_audio_should_resolve_context_when_message_id_provided(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        message = SimpleNamespace(id=uuid4(), answer="history")
        conversation = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "_get_valid_message", lambda *_args, **_kwargs: (message, conversation))
        monkeypatch.setattr(service, "_resolve_voice", lambda *_args, **_kwargs: "diana")
        captures = {}
        monkeypatch.setattr(
            service,
            "_create_tts_response",
            lambda input_text, voice: captures.update({"input_text": input_text, "voice": voice}) or "resp",
        )
        monkeypatch.setattr(
            service,
            "_stream_tts_response",
            lambda response, common_data: iter([f"{response}:{common_data['conversation_id']}:{common_data['message_id']}"]),
        )

        events = list(service.text_to_audio(message_id=str(message.id), text="hello", account=account))

        assert captures["voice"] == "diana"
        assert events == [f"resp:{conversation.id}:{message.id}"]

    def test_get_valid_message_should_raise_when_message_not_accessible(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())

        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)
        with pytest.raises(NotFoundException):
            service._get_valid_message(message_id=uuid4(), account=account)

        foreign_message = SimpleNamespace(
            is_deleted=False,
            created_by=uuid4(),
            conversation=SimpleNamespace(is_deleted=False, created_by=account.id),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: foreign_message)
        with pytest.raises(NotFoundException):
            service._get_valid_message(message_id=uuid4(), account=account)

    def test_get_valid_message_should_raise_when_conversation_not_accessible(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        message = SimpleNamespace(
            is_deleted=False,
            created_by=account.id,
            conversation=None,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: message)

        with pytest.raises(NotFoundException):
            service._get_valid_message(message_id=uuid4(), account=account)

    def test_get_valid_message_should_return_message_and_conversation(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        conversation = SimpleNamespace(is_deleted=False, created_by=account.id)
        message = SimpleNamespace(
            id=uuid4(),
            is_deleted=False,
            created_by=account.id,
            conversation=conversation,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: message)

        result_message, result_conversation = service._get_valid_message(message_id=message.id, account=account)

        assert result_message is message
        assert result_conversation is conversation

    def test_resolve_voice_should_raise_for_service_api_messages(self):
        service = _build_service()
        message = SimpleNamespace(invoke_from=InvokeFrom.SERVICE_API.value)

        with pytest.raises(NotFoundException):
            service._resolve_voice(
                message=message,
                conversation=SimpleNamespace(app_id=uuid4()),
                account=SimpleNamespace(id=uuid4()),
            )

    def test_resolve_voice_should_fallback_to_alex_when_voice_is_invalid(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(
            account_id=account.id,
            status=AppStatus.PUBLISHED.value,
            draft_app_config=SimpleNamespace(text_to_speech={"enable": True, "voice": "invalid-voice"}),
            app_config=SimpleNamespace(text_to_speech={"enable": True, "voice": "alex"}),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)

        voice = service._resolve_voice(
            message=SimpleNamespace(invoke_from=InvokeFrom.DEBUGGER.value),
            conversation=SimpleNamespace(app_id=uuid4()),
            account=account,
        )

        assert voice == "alex"

    def test_resolve_voice_should_raise_when_web_or_debug_app_not_found(self, monkeypatch):
        service = _build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service._resolve_voice(
                message=SimpleNamespace(invoke_from=InvokeFrom.WEB_APP.value),
                conversation=SimpleNamespace(app_id=uuid4()),
                account=SimpleNamespace(id=uuid4()),
            )

    def test_resolve_voice_should_raise_when_debugger_app_not_owned(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(
            account_id=uuid4(),
            status=AppStatus.PUBLISHED.value,
            draft_app_config=SimpleNamespace(text_to_speech={"enable": True, "voice": "alex"}),
            app_config=SimpleNamespace(text_to_speech={"enable": True, "voice": "alex"}),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)

        with pytest.raises(NotFoundException):
            service._resolve_voice(
                message=SimpleNamespace(invoke_from=InvokeFrom.DEBUGGER.value),
                conversation=SimpleNamespace(app_id=uuid4()),
                account=account,
            )

    def test_resolve_voice_should_raise_when_web_app_unpublished(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(
            account_id=account.id,
            status=AppStatus.DRAFT.value,
            draft_app_config=SimpleNamespace(text_to_speech={"enable": True, "voice": "alex"}),
            app_config=SimpleNamespace(text_to_speech={"enable": True, "voice": "alex"}),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)

        with pytest.raises(NotFoundException):
            service._resolve_voice(
                message=SimpleNamespace(invoke_from=InvokeFrom.WEB_APP.value),
                conversation=SimpleNamespace(app_id=uuid4()),
                account=account,
            )

    def test_resolve_voice_should_raise_when_text_to_speech_disabled(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(
            account_id=account.id,
            status=AppStatus.PUBLISHED.value,
            draft_app_config=SimpleNamespace(text_to_speech={"enable": True, "voice": "alex"}),
            app_config=SimpleNamespace(text_to_speech={"enable": False, "voice": "alex"}),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)

        with pytest.raises(FailException):
            service._resolve_voice(
                message=SimpleNamespace(invoke_from=InvokeFrom.WEB_APP.value),
                conversation=SimpleNamespace(app_id=uuid4()),
                account=account,
            )

    def test_resolve_voice_should_use_assistant_agent_default_voice(self):
        service = _build_service()

        voice = service._resolve_voice(
            message=SimpleNamespace(invoke_from=InvokeFrom.ASSISTANT_AGENT.value),
            conversation=SimpleNamespace(app_id=uuid4()),
            account=SimpleNamespace(id=uuid4()),
        )

        assert voice == "alex"

    def test_resolve_voice_should_fallback_to_default_when_invoke_from_unknown(self):
        service = _build_service()

        voice = service._resolve_voice(
            message=SimpleNamespace(invoke_from="unknown-source"),
            conversation=SimpleNamespace(app_id=uuid4()),
            account=SimpleNamespace(id=uuid4()),
        )

        assert voice == "alex"

    def test_resolve_voice_should_return_valid_configured_voice(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(
            account_id=account.id,
            status=AppStatus.PUBLISHED.value,
            draft_app_config=SimpleNamespace(text_to_speech={"enable": True, "voice": "alex"}),
            app_config=SimpleNamespace(text_to_speech={"enable": True, "voice": "anna"}),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)

        voice = service._resolve_voice(
            message=SimpleNamespace(invoke_from=InvokeFrom.WEB_APP.value),
            conversation=SimpleNamespace(app_id=uuid4()),
            account=account,
        )

        assert voice == "anna"

    def test_stream_tts_response_should_emit_message_and_end_events(self):
        response = _DummyResponse(chunks=[b"a", b"b"], raise_error=False)
        common_data = {"conversation_id": "c1", "message_id": "m1", "audio": ""}

        events = list(AudioService._stream_tts_response(response=response, common_data=common_data))

        assert any(event.startswith("event: tts_message") for event in events)
        assert events[-1].startswith("event: tts_end")
        assert response.closed is True

    def test_stream_tts_response_should_emit_error_event_on_exception(self):
        response = _DummyResponse(chunks=[], raise_error=True)
        common_data = {"conversation_id": "c1", "message_id": "m1", "audio": ""}

        events = list(AudioService._stream_tts_response(response=response, common_data=common_data))

        assert any(event.startswith("event: tts_error") for event in events)
        assert response.closed is True

    def test_stream_tts_response_should_skip_empty_chunks(self):
        response = _DummyResponse(chunks=[b"", b"a"], raise_error=False)
        common_data = {"conversation_id": "c1", "message_id": "m1", "audio": ""}

        events = list(AudioService._stream_tts_response(response=response, common_data=common_data))

        message_events = [event for event in events if event.startswith("event: tts_message")]
        assert len(message_events) == 1
        assert events[-1].startswith("event: tts_end")

    def test_create_tts_response_should_raise_fail_exception_when_request_fails(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")
        monkeypatch.setattr(
            "internal.service.audio_service.requests.post",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.exceptions.RequestException("boom")),
        )

        with pytest.raises(FailException):
            service._create_tts_response(input_text="hello", voice="alex")

    def test_create_tts_response_should_raise_when_siliconflow_config_missing(self, monkeypatch):
        service = _build_service()
        monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
        monkeypatch.delenv("SILICONFLOW_API_BASE", raising=False)

        with pytest.raises(FailException, match="语音服务配置缺失"):
            service._create_tts_response(input_text="hello", voice="alex")

    def test_create_tts_response_should_raise_balance_insufficient_when_http_403(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")

        class _Response:
            status_code = 403

            @staticmethod
            def json():
                return {"message": "balance is insufficient"}

            def raise_for_status(self):
                raise requests.exceptions.HTTPError("forbidden", response=self)

        monkeypatch.setattr("internal.service.audio_service.requests.post", lambda *_args, **_kwargs: _Response())

        with pytest.raises(FailException, match="余额不足"):
            service._create_tts_response(input_text="hello", voice="alex")

    def test_create_tts_response_should_raise_permission_denied_when_http_403_without_balance_message(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")

        class _Response:
            status_code = 403

            @staticmethod
            def json():
                return {"message": "forbidden by policy"}

            def raise_for_status(self):
                raise requests.exceptions.HTTPError("forbidden", response=self)

        monkeypatch.setattr("internal.service.audio_service.requests.post", lambda *_args, **_kwargs: _Response())

        with pytest.raises(FailException, match="访问被拒绝"):
            service._create_tts_response(input_text="hello", voice="alex")

    def test_create_tts_response_should_raise_rate_limited_when_http_429(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")

        class _Response:
            status_code = 429

            @staticmethod
            def json():
                return {"message": "too many requests"}

            def raise_for_status(self):
                raise requests.exceptions.HTTPError("too-many-requests", response=self)

        monkeypatch.setattr("internal.service.audio_service.requests.post", lambda *_args, **_kwargs: _Response())

        with pytest.raises(FailException, match="请求过于频繁"):
            service._create_tts_response(input_text="hello", voice="alex")

    def test_create_tts_response_should_keep_generic_message_for_unmapped_http_status(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")

        class _Response:
            status_code = 500

            @staticmethod
            def json():
                return {"message": "server error"}

            def raise_for_status(self):
                raise requests.exceptions.HTTPError("server-error", response=self)

        monkeypatch.setattr("internal.service.audio_service.requests.post", lambda *_args, **_kwargs: _Response())

        with pytest.raises(FailException, match="文字转语音请求失败，请稍后重试"):
            service._create_tts_response(input_text="hello", voice="alex")

    def test_create_tts_response_should_fallback_to_generic_message_when_error_response_not_json(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")

        class _Response:
            status_code = 500

            @staticmethod
            def json():
                raise ValueError("not-json")

            def raise_for_status(self):
                raise requests.exceptions.HTTPError("server-error", response=self)

        monkeypatch.setattr("internal.service.audio_service.requests.post", lambda *_args, **_kwargs: _Response())

        with pytest.raises(FailException, match="文字转语音请求失败，请稍后重试"):
            service._create_tts_response(input_text="hello", voice="alex")

    def test_create_tts_response_should_raise_access_denied_when_http_403_without_balance_message(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")

        class _Response:
            status_code = 403

            @staticmethod
            def json():
                return {"message": "permission denied"}

            def raise_for_status(self):
                raise requests.exceptions.HTTPError("forbidden", response=self)

        monkeypatch.setattr("internal.service.audio_service.requests.post", lambda *_args, **_kwargs: _Response())

        with pytest.raises(FailException, match="访问被拒绝"):
            service._create_tts_response(input_text="hello", voice="alex")

    def test_create_tts_response_should_keep_default_message_when_http_error_body_not_json(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")

        class _Response:
            status_code = 403

            @staticmethod
            def json():
                raise ValueError("invalid json")

            def raise_for_status(self):
                raise requests.exceptions.HTTPError("forbidden", response=self)

        monkeypatch.setattr("internal.service.audio_service.requests.post", lambda *_args, **_kwargs: _Response())

        with pytest.raises(FailException, match="文字转语音请求失败，请稍后重试"):
            service._create_tts_response(input_text="hello", voice="alex")

    def test_create_tts_response_should_return_response_when_request_succeeds(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")
        captures = {}

        class _Response:
            def raise_for_status(self):
                return None

        response = _Response()

        def _fake_post(url, **kwargs):
            captures["url"] = url
            captures["kwargs"] = kwargs
            return response

        monkeypatch.setattr("internal.service.audio_service.requests.post", _fake_post)

        result = service._create_tts_response(input_text="hello", voice="anna")

        assert result is response
        assert captures["url"] == "https://api.example.com/v1/audio/speech"
        assert captures["kwargs"]["json"]["voice"] == "FunAudioLLM/CosyVoice2-0.5B:anna"
        assert captures["kwargs"]["stream"] is True

    def test_create_tts_response_should_raise_fail_exception_on_unexpected_error(self, monkeypatch):
        service = _build_service()
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
        monkeypatch.setenv("SILICONFLOW_API_BASE", "https://api.example.com")
        monkeypatch.setattr(
            "internal.service.audio_service.requests.post",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("boom")),
        )

        with pytest.raises(FailException):
            service._create_tts_response(input_text="hello", voice="alex")
