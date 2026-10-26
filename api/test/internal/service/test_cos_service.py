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


class TestCosService:
    def _build_service(self):
        return CosService(upload_file_service=SimpleNamespace(create_upload_file=lambda **kwargs: SimpleNamespace(**kwargs)))

    def test_upload_file_should_reject_unsupported_extension(self):
        service = self._build_service()
        file = FileStorage(stream=BytesIO(b"abc"), filename="malware.exe", content_type="application/octet-stream")

        with pytest.raises(FailException):
            service.upload_file(file=file, only_image=False, account=SimpleNamespace(id=uuid4()))

    def test_upload_file_should_reject_non_image_when_only_image_enabled(self):
        service = self._build_service()
        file = FileStorage(stream=BytesIO(b"abc"), filename="readme.txt", content_type="text/plain")

        with pytest.raises(FailException):
            service.upload_file(file=file, only_image=True, account=SimpleNamespace(id=uuid4()))

    def test_upload_file_should_put_object_and_create_upload_record(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        captured = {}

        class _Client:
            def put_object(self, bucket, file_content, upload_filename):
                captured["bucket"] = bucket
                captured["file_content"] = file_content
                captured["upload_filename"] = upload_filename

        def _create_upload_file(**kwargs):
            captured["upload_payload"] = kwargs
            return SimpleNamespace(**kwargs)

        service = CosService(
            upload_file_service=SimpleNamespace(create_upload_file=_create_upload_file)
        )
        monkeypatch.setattr(CosService, "_get_client", classmethod(lambda cls: _Client()))
        monkeypatch.setattr(CosService, "_get_bucket", classmethod(lambda cls: "test-bucket"))
        monkeypatch.setattr(
            "internal.service.cos_service.utc_now_naive",
            lambda: datetime(2026, 1, 2, 3, 4, 5),
        )
        file = FileStorage(stream=BytesIO(b"hello"), filename="demo.txt", content_type="text/plain")

        result = service.upload_file(file=file, only_image=False, account=account)

        assert captured["bucket"] == "test-bucket"
        assert captured["file_content"] == b"hello"
        assert captured["upload_filename"].startswith("2026/01/02/")
        assert captured["upload_payload"]["account_id"] == account.id
        assert captured["upload_payload"]["extension"] == "txt"
        assert captured["upload_payload"]["size"] == 5
        assert result.name == "demo.txt"
        assert result.extension == "txt"

    def test_upload_file_should_accept_uppercase_extension_and_normalize_lowercase(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        captured = {}

        class _Client:
            @staticmethod
            def put_object(_bucket, _file_content, _upload_filename):
                return None

        def _create_upload_file(**kwargs):
            captured["upload_payload"] = kwargs
            return SimpleNamespace(**kwargs)

        service = CosService(
            upload_file_service=SimpleNamespace(create_upload_file=_create_upload_file)
        )
        monkeypatch.setattr(CosService, "_get_client", classmethod(lambda cls: _Client()))
        monkeypatch.setattr(CosService, "_get_bucket", classmethod(lambda cls: "test-bucket"))
        file = FileStorage(stream=BytesIO(b"image"), filename="avatar.PNG", content_type="image/png")

        result = service.upload_file(file=file, only_image=True, account=account)

        assert result.extension == "png"
        assert captured["upload_payload"]["extension"] == "png"

    def test_get_file_url_should_use_custom_domain_when_present(self, monkeypatch):
        monkeypatch.setenv("COS_DOMAIN", "https://cos.example.com")

        url = CosService.get_file_url("2026/01/01/demo.txt")

        assert url == "https://cos.example.com/2026/01/01/demo.txt"

    def test_get_file_url_should_build_domain_from_bucket_when_custom_domain_missing(self, monkeypatch):
        monkeypatch.delenv("COS_DOMAIN", raising=False)
        monkeypatch.setenv("COS_BUCKET", "bucket-a")
        monkeypatch.setenv("COS_SCHEME", "https")
        monkeypatch.setenv("COS_REGION", "ap-shanghai")

        url = CosService.get_file_url("demo.txt")

        assert url == "https://bucket-a.cos.ap-shanghai.myqcloud.com/demo.txt"

    def test_get_file_url_should_return_plain_url_for_anonymous_downloads(self, monkeypatch):
        monkeypatch.setenv("COS_DOMAIN", "https://cos.example.com")

        url = CosService.get_file_url(
            "2026/01/01/demo.txt",
            download_name="上海迪士尼及周边7天旅行计划.txt",
        )

        assert url == "https://cos.example.com/2026/01/01/demo.txt"

    def test_get_file_url_should_reject_local_keys(self):
        with pytest.raises(FailException, match="本地文件存储已禁用"):
            CosService.get_file_url("local/2026/01/01/demo.txt")

    @pytest.mark.parametrize(
        ("download_name", "expected_disposition"),
        [("上海旅行计划.txt", "attachment"), ("preview.html", "inline"), ("preview.HTM", "inline")],
    )
    def test_get_file_url_should_choose_presigned_disposition_by_file_type(
        self, monkeypatch, download_name, expected_disposition,
    ):
        monkeypatch.setenv("COS_DOMAIN", "https://cos.example.com")
        monkeypatch.setenv("COS_PRESIGNED_DOWNLOAD_URL_EXPIRE_SECONDS", "600")

        class _Client:
            @staticmethod
            def get_presigned_download_url(*, Bucket, Key, Expired, Params):
                assert Bucket == "bucket-a"
                assert Key == "2026/01/01/demo.txt"
                assert Expired == 600
                assert Params["response-content-disposition"].startswith(f"{expected_disposition}; filename=\"")
                return "https://signed.example.com/demo.txt?signature=1"

        monkeypatch.setattr(CosService, "_get_client", classmethod(lambda cls: _Client()))
        monkeypatch.setattr(CosService, "_get_bucket", classmethod(lambda cls: "bucket-a"))

        url = CosService.get_file_url(
            "2026/01/01/demo.txt",
            download_name=download_name,
        )

        assert url == "https://signed.example.com/demo.txt?signature=1"

    def test_upload_bytes_without_record_should_upload_and_return_public_url(self, monkeypatch):
        captured = {}

        class _Client:
            @staticmethod
            def put_object(bucket, file_content, upload_filename):
                captured["bucket"] = bucket
                captured["file_content"] = file_content
                captured["upload_filename"] = upload_filename

        monkeypatch.setattr(CosService, "_get_client", classmethod(lambda cls: _Client()))
        monkeypatch.setattr(CosService, "_get_bucket", classmethod(lambda cls: "test-bucket"))
        monkeypatch.setattr(CosService, "get_file_url", classmethod(lambda cls, key, download_name=None: f"https://cos.example.com/{key}"))
        monkeypatch.setattr(
            "internal.service.cos_service.utc_now_naive",
            lambda: datetime(2026, 1, 2, 3, 4, 5),
        )

        url = CosService.upload_bytes_without_record(
            filename="look.png",
            content=b"image",
            folder="generated-images",
        )

        assert captured["bucket"] == "test-bucket"
        assert captured["file_content"] == b"image"
        assert "/generated-images/" in captured["upload_filename"]
        assert url.startswith("https://cos.example.com/2026/01/02/generated-images/")

    def test_upload_bytes_without_record_should_raise_when_cos_upload_failed(self, monkeypatch):
        class _Client:
            @staticmethod
            def put_object(*_args, **_kwargs):
                raise RuntimeError("cos-down")

        monkeypatch.setattr(CosService, "_get_client", classmethod(lambda cls: _Client()))
        monkeypatch.setattr(CosService, "_get_bucket", classmethod(lambda cls: "test-bucket"))
        monkeypatch.setattr(
            "internal.service.cos_service.utc_now_naive",
            lambda: datetime(2026, 1, 2, 3, 4, 5),
        )

        with pytest.raises(FailException, match="上传产物文件失败"):
            CosService.upload_bytes_without_record(
                filename="look.png",
                content=b"image",
                folder="generated-images",
            )

    def test_download_file_should_delegate_to_cos_client(self, monkeypatch):
        captured = {}

        class _Client:
            def download_file(self, bucket, key, target_file_path):
                captured["bucket"] = bucket
                captured["key"] = key
                captured["target_file_path"] = target_file_path

        monkeypatch.setattr(CosService, "_get_client", classmethod(lambda cls: _Client()))
        monkeypatch.setattr(CosService, "_get_bucket", classmethod(lambda cls: "test-bucket"))

        service = self._build_service()
        service.download_file("2026/01/01/demo.txt", "/tmp/demo.txt")

        assert captured == {
            "bucket": "test-bucket",
            "key": "2026/01/01/demo.txt",
            "target_file_path": "/tmp/demo.txt",
        }

    def test_download_file_should_reject_local_keys(self):
        service = self._build_service()

        with pytest.raises(FailException, match="本地文件存储已禁用"):
            service.download_file("local/2026/01/01/demo.txt", "/tmp/demo.txt")

    def test_upload_file_should_raise_when_cos_upload_failed(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())

        class _Client:
            @staticmethod
            def put_object(*_args, **_kwargs):
                raise RuntimeError("cos-down")

        service = CosService(
            upload_file_service=SimpleNamespace(create_upload_file=lambda **kwargs: SimpleNamespace(**kwargs))
        )
        monkeypatch.setattr(CosService, "_get_client", classmethod(lambda cls: _Client()))
        monkeypatch.setattr(CosService, "_get_bucket", classmethod(lambda cls: "test-bucket"))
        monkeypatch.setattr("internal.service.cos_service.time.sleep", lambda *_args, **_kwargs: None)
        file = FileStorage(stream=BytesIO(b"hello"), filename="demo.txt", content_type="text/plain")

        with pytest.raises(FailException):
            service.upload_file(file=file, only_image=False, account=account)

    def test_upload_file_should_retry_transient_errors_then_succeed(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        call_state = {"count": 0}
        sleeps = []
        captured = {}

        class _Client:
            @staticmethod
            def put_object(bucket, file_content, upload_filename):
                call_state["count"] += 1
                if call_state["count"] < 3:
                    raise RuntimeError("temporary network error")
                captured["bucket"] = bucket
                captured["file_content"] = file_content
                captured["upload_filename"] = upload_filename

        def _create_upload_file(**kwargs):
            captured["upload_payload"] = kwargs
            return SimpleNamespace(**kwargs)

        service = CosService(
            upload_file_service=SimpleNamespace(create_upload_file=_create_upload_file)
        )
        monkeypatch.setattr(CosService, "_get_client", classmethod(lambda cls: _Client()))
        monkeypatch.setattr(CosService, "_get_bucket", classmethod(lambda cls: "test-bucket"))
        monkeypatch.setattr("internal.service.cos_service.time.sleep", lambda seconds: sleeps.append(seconds))
        file = FileStorage(stream=BytesIO(b"hello"), filename="demo.txt", content_type="text/plain")

        result = service.upload_file(file=file, only_image=False, account=account)

        assert call_state["count"] == 3
        assert sleeps == [0.1, 0.2]
        assert captured["bucket"] == "test-bucket"
        assert captured["file_content"] == b"hello"
        assert captured["upload_payload"]["account_id"] == account.id
        assert result.name == "demo.txt"

    def test_upload_file_should_treat_already_exists_error_as_idempotent_success(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        call_state = {"count": 0}
        captured = {}

        class _Client:
            @staticmethod
            def put_object(*_args, **_kwargs):
                call_state["count"] += 1
                raise RuntimeError("ObjectAlreadyExists: duplicate key")

        def _create_upload_file(**kwargs):
            captured["upload_payload"] = kwargs
            return SimpleNamespace(**kwargs)

        service = CosService(
            upload_file_service=SimpleNamespace(create_upload_file=_create_upload_file)
        )
        monkeypatch.setattr(CosService, "_get_client", classmethod(lambda cls: _Client()))
        monkeypatch.setattr(CosService, "_get_bucket", classmethod(lambda cls: "test-bucket"))
        monkeypatch.setattr("internal.service.cos_service.time.sleep", lambda *_args, **_kwargs: None)
        file = FileStorage(stream=BytesIO(b"hello"), filename="demo.txt", content_type="text/plain")

        result = service.upload_file(file=file, only_image=False, account=account)

        assert call_state["count"] == 1
        assert captured["upload_payload"]["name"] == "demo.txt"
        assert result.name == "demo.txt"

    def test_get_client_should_build_cos_client_from_env(self, monkeypatch):
        captured = {}
        monkeypatch.setenv("COS_REGION", "ap-shanghai")
        monkeypatch.setenv("COS_SECRET_ID", "sid")
        monkeypatch.setenv("COS_SECRET_KEY", "skey")
        monkeypatch.setenv("COS_SCHEME", "https")
        monkeypatch.setenv("COS_TIMEOUT_SECONDS", "12")
        monkeypatch.setenv("COS_SDK_RETRY", "2")
        monkeypatch.setenv("COS_AUTO_SWITCH_DOMAIN_ON_RETRY", "true")
        monkeypatch.setenv("COS_ENABLE_OLD_DOMAIN", "false")
        monkeypatch.setenv("COS_ENABLE_INTERNAL_DOMAIN", "false")

        def _fake_cos_config(**kwargs):
            captured["config_kwargs"] = kwargs
            return SimpleNamespace(**kwargs)

        def _fake_cos_client(conf, retry):
            captured["config"] = conf
            captured["retry"] = retry
            return "cos-client"

        monkeypatch.setattr("internal.service.cos_service.CosConfig", _fake_cos_config)
        monkeypatch.setattr("internal.service.cos_service.CosS3Client", _fake_cos_client)

        client = CosService._get_client()

        assert client == "cos-client"
        assert captured["config_kwargs"]["Region"] == "ap-shanghai"
        assert captured["config_kwargs"]["SecretId"] == "sid"
        assert captured["config_kwargs"]["SecretKey"] == "skey"
        assert captured["config_kwargs"]["Scheme"] == "https"
        assert captured["config_kwargs"]["Timeout"] == 12
        assert captured["config_kwargs"]["AutoSwitchDomainOnRetry"] is True
        assert captured["config_kwargs"]["EnableOldDomain"] is False
        assert captured["config_kwargs"]["EnableInternalDomain"] is False
        assert captured["retry"] == 2

    def test_get_client_should_use_default_timeout_and_retry_when_env_missing(self, monkeypatch):
        captured = {}
        monkeypatch.setenv("COS_REGION", "ap-shanghai")
        monkeypatch.setenv("COS_SECRET_ID", "sid")
        monkeypatch.setenv("COS_SECRET_KEY", "skey")
        monkeypatch.setenv("COS_SCHEME", "https")
        monkeypatch.delenv("COS_TIMEOUT_SECONDS", raising=False)
        monkeypatch.delenv("COS_SDK_RETRY", raising=False)

        def _fake_cos_config(**kwargs):
            captured["config_kwargs"] = kwargs
            return SimpleNamespace(**kwargs)

        def _fake_cos_client(conf, retry):
            captured["config"] = conf
            captured["retry"] = retry
            return "cos-client"

        monkeypatch.setattr("internal.service.cos_service.CosConfig", _fake_cos_config)
        monkeypatch.setattr("internal.service.cos_service.CosS3Client", _fake_cos_client)

        client = CosService._get_client()

        assert client == "cos-client"
        assert captured["config_kwargs"]["Timeout"] == 10
        assert captured["retry"] == 1

    def test_get_upload_max_attempts_should_use_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("COS_UPLOAD_MAX_ATTEMPTS", raising=False)

        assert CosService._get_upload_max_attempts() == 3

    def test_get_upload_max_attempts_should_read_env_value(self, monkeypatch):
        monkeypatch.setenv("COS_UPLOAD_MAX_ATTEMPTS", "5")

        assert CosService._get_upload_max_attempts() == 5

    def test_get_timeout_seconds_should_use_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("COS_TIMEOUT_SECONDS", raising=False)

        assert CosService._get_timeout_seconds() == 10

    def test_get_timeout_seconds_should_read_env_value(self, monkeypatch):
        monkeypatch.setenv("COS_TIMEOUT_SECONDS", "12")

        assert CosService._get_timeout_seconds() == 12

    def test_get_sdk_retry_should_use_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("COS_SDK_RETRY", raising=False)

        assert CosService._get_sdk_retry() == 1

    def test_get_sdk_retry_should_read_env_value(self, monkeypatch):
        monkeypatch.setenv("COS_SDK_RETRY", "5")

        assert CosService._get_sdk_retry() == 5

    def test_get_bucket_should_read_env_bucket_name(self, monkeypatch):
        monkeypatch.setenv("COS_BUCKET", "demo-bucket")

        assert CosService._get_bucket() == "demo-bucket"

    def test_get_int_env_should_fallback_for_invalid_values(self, monkeypatch):
        monkeypatch.setenv("COS_TIMEOUT_SECONDS", "invalid")
        monkeypatch.setenv("COS_SDK_RETRY", "-5")

        assert CosService._get_int_env("COS_TIMEOUT_SECONDS", 10) == 10
        assert CosService._get_int_env("COS_SDK_RETRY", 1, minimum=0) == 0

    def test_get_bool_env_should_fallback_for_invalid_values(self, monkeypatch):
        monkeypatch.setenv("COS_AUTO_SWITCH_DOMAIN_ON_RETRY", "maybe")

        assert CosService._get_bool_env("COS_AUTO_SWITCH_DOMAIN_ON_RETRY", True) is True

    def test_upload_with_retry_should_return_immediately_when_max_attempts_is_zero(self):
        service = self._build_service()
        client = SimpleNamespace(
            put_object=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("put_object should not be called when max_attempts is zero")
            )
        )

        service._upload_with_retry(
            client=client,
            bucket="bucket",
            file_content=b"data",
            upload_filename="key",
            max_attempts=0,
        )

    @pytest.mark.parametrize(
        "message",
        [
            "ObjectAlreadyExists: duplicate key",
            "file already exists",
            "Key already exists in bucket",
            "FILEALREADYEXISTS",
        ],
    )
    def test_is_object_already_exists_error_should_match_common_patterns(self, message):
        service = self._build_service()

        assert service._is_object_already_exists_error(RuntimeError(message)) is True

    def test_is_object_already_exists_error_should_return_false_for_unrelated_error(self):
        service = self._build_service()

        assert service._is_object_already_exists_error(RuntimeError("network timeout")) is False
