import logging
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests
from PIL import Image

from internal.exception import FailException
from internal.service.icon_generator_service import (
    IconGenerationRejectedError,
    IconGeneratorService,
    IconStorageError,
)

_ORIGINAL_GENERATE_ICON_PROMPT = IconGeneratorService._generate_icon_prompt


def _build_service(cos_service=None, language_model_manager=None):
    """构建测试用的 IconGeneratorService"""
    return IconGeneratorService(
        cos_service=cos_service or SimpleNamespace(
            _get_client=Mock(return_value=Mock()),
            _get_bucket=Mock(return_value="test-bucket"),
        ),
        language_model_manager=language_model_manager or SimpleNamespace(
            get_default_model=Mock(return_value=Mock())
        ),
    )


def _mock_safe_request(response, snapshot=None):
    def _safe_request(method, url, **kwargs):
        if snapshot is not None:
            snapshot.update(
                {
                    "method": method,
                    "url": url,
                    "kwargs": kwargs,
                }
            )
        return response

    return _safe_request


def _image_bytes(image_format="PNG"):
    image = Image.new("RGB", (2, 2), color=(20, 80, 160))
    output = BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


def _mock_image_response(image_data):
    response = Mock()
    response.headers = {"Content-Length": str(len(image_data))}
    response.iter_content.return_value = [image_data]
    response.raise_for_status = Mock()
    return response


@pytest.fixture(autouse=True)
def _mock_icon_prompt_generation(monkeypatch):
    """默认阻断提示词外部调用，避免测试触发真实网络重试。"""
    monkeypatch.setattr(
        IconGeneratorService,
        "_generate_icon_prompt",
        lambda _self, _name, _description: "A stable mocked icon prompt",
    )


class TestIconGeneratorService:
    def test_generate_icon_with_kolors_success(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {
            "SILICONFLOW_API_KEY": "test-key",
            "COS_DOMAIN": "https://test.cos.com",
        }
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        mock_response = Mock()
        mock_response.json.return_value = {
            "images": [{"url": "https://kolors.com/image.png"}]
        }
        mock_response.raise_for_status = Mock()

        mock_download_response = _mock_image_response(_image_bytes())

        with patch(
            "internal.service.icon_generator_service.safe_request",
            side_effect=[
                mock_response,
                mock_download_response,
            ],
        ):
                mock_cos_client = Mock()
                mock_cos_service = SimpleNamespace(
                    _get_client=Mock(return_value=mock_cos_client),
                    _get_bucket=Mock(return_value="test-bucket"),
                )

                service = _build_service(cos_service=mock_cos_service)
                icon_url = service.generate_icon("测试应用", "这是一个测试应用")

                assert icon_url.startswith("https://test.cos.com/")
                assert "/icons/kolors_" in icon_url
                mock_cos_client.put_object.assert_called_once()

    def test_generate_icon_should_fallback_to_qwen_when_kolors_rate_limited(self, monkeypatch, caplog):
        mock_app = Mock()
        mock_app.config = {"SILICONFLOW_API_KEY": "test-key", "COS_DOMAIN": "https://test.cos.com"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        service = _build_service()
        monkeypatch.setattr(
            service,
            "_generate_with_kolors",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(FailException("Kolors 服务请求过于频繁，请稍后重试")),
        )
        monkeypatch.setattr(service, "_generate_with_qwen", lambda *_args, **_kwargs: "https://qwen/icon.png")

        with caplog.at_level(logging.INFO):
            icon_url = service.generate_icon("ICON_USER_NAME_SECRET", "ICON_USER_DESCRIPTION_SECRET")

        assert icon_url == "https://qwen/icon.png"
        assert "provider=Kolors model=Kwai-Kolors/Kolors attempt=1 status=failed" in caplog.text
        assert "error_class=provider_error fallback=Qwen" in caplog.text
        assert "provider=Qwen model=Qwen/Qwen-Image attempt=2 status=success" in caplog.text
        assert "ICON_USER_NAME_SECRET" not in caplog.text
        assert "ICON_USER_DESCRIPTION_SECRET" not in caplog.text
        assert "https://qwen/icon.png" not in caplog.text

    def test_generate_icon_should_fallback_to_dalle_when_siliconflow_providers_rate_limited(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {
            "SILICONFLOW_API_KEY": "test-key",
            "OPENAI_API_KEY": "openai-key",
            "COS_DOMAIN": "https://test.cos.com",
        }
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        service = _build_service()
        monkeypatch.setattr(
            service,
            "_generate_with_kolors",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(FailException("Kolors 服务请求过于频繁，请稍后重试")),
        )
        monkeypatch.setattr(
            service,
            "_generate_with_qwen",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(FailException("Qwen 服务请求过于频繁，请稍后重试")),
        )
        monkeypatch.setattr(service, "_generate_with_dalle", lambda *_args, **_kwargs: "https://dalle/icon.png")

        icon_url = service.generate_icon("测试应用", "desc")

        assert icon_url == "https://dalle/icon.png"

    def test_generate_icon_reuses_one_prompt_across_provider_fallbacks(self, monkeypatch):
        app = Mock()
        app.config = {"SILICONFLOW_API_KEY": "test-key", "OPENAI_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", app)
        service = _build_service()
        prompt = Mock(return_value="one prompt")
        monkeypatch.setattr(service, "_generate_icon_prompt", prompt)
        provider_prompts = []

        def request(provider, _model, prompt, _source, **_kwargs):
            provider_prompts.append((provider, prompt))
            raise FailException("provider unavailable")

        monkeypatch.setattr(service, "_request_siliconflow_image", request)
        monkeypatch.setattr(service, "_download_and_upload_image", lambda *_args: "https://dalle/icon.png")
        monkeypatch.setattr(
            "internal.service.icon_generator_service.DallEAPIWrapper",
            lambda **_kwargs: SimpleNamespace(
                run=lambda prompt: provider_prompts.append(("DALLE", prompt)) or "https://dalle/image.png"
            ),
        )

        result = service.generate_icon("测试应用", "desc")

        assert result.endswith("icon.png")
        prompt.assert_called_once_with("测试应用", "desc")
        assert provider_prompts == [(provider, "one prompt") for provider in ("Kolors", "Qwen", "DALLE")]

    def test_generate_icon_all_services_fail(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {
            "SILICONFLOW_API_KEY": None,
            "OPENAI_API_KEY": None,
        }
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        service = _build_service()

        with pytest.raises(FailException, match="图标生成服务暂时不可用"):
            service.generate_icon("测试应用", "这是一个测试应用")

    def test_generate_icon_prompt_should_return_llm_output_without_extra_suffix(self, monkeypatch):
        monkeypatch.setattr(
            IconGeneratorService,
            "_generate_icon_prompt",
            _ORIGINAL_GENERATE_ICON_PROMPT,
        )

        class _Pipe:
            def __or__(self, _other):
                return self

            @staticmethod
            def invoke(_payload):
                return "  A polished business app icon prompt  "

        monkeypatch.setattr(
            "internal.service.icon_generator_service.ChatPromptTemplate.from_template",
            lambda _template: _Pipe(),
        )
        monkeypatch.setattr(
            "internal.core.language_model.providers.deepseek.chat.Chat",
            lambda **_kwargs: object(),
        )

        service = _build_service()
        prompt = service._generate_icon_prompt("测试应用", "desc")

        assert prompt == "A polished business app icon prompt"

    def test_generate_icon_prompt_should_fallback_to_default_when_llm_raises(self, monkeypatch, caplog):
        monkeypatch.setattr(
            IconGeneratorService,
            "_generate_icon_prompt",
            _ORIGINAL_GENERATE_ICON_PROMPT,
        )
        monkeypatch.setattr(
            "internal.core.language_model.providers.deepseek.chat.Chat",
            lambda **_kwargs: object(),
        )

        def _raise_template_error(_template):
            raise RuntimeError("synthetic-prompt-secret")

        monkeypatch.setattr(
            "internal.service.icon_generator_service.ChatPromptTemplate.from_template",
            _raise_template_error,
        )

        service = _build_service()
        prompt = service._generate_icon_prompt("测试应用", "desc")

        assert "mobile app launcher icon" in prompt
        assert "rounded square app icon composition" in prompt
        assert "no text, no watermark, no extra elements" in prompt
        assert "synthetic-prompt-secret" not in caplog.text
        assert "error_type=RuntimeError" in caplog.text

    def test_missing_cos_domain_rejects_before_download_or_upload(self, monkeypatch):
        app = Mock()
        app.config = {}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", app)
        network_request = Mock()
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", network_request)
        cos_client = Mock()
        service = _build_service(cos_service=SimpleNamespace(
            _get_client=Mock(return_value=cos_client),
            _get_bucket=Mock(return_value="test-bucket"),
        ))

        with pytest.raises(FailException, match="COS_DOMAIN 未配置"):
            service._download_and_upload_image("https://example.com/icon.png", "kolors")

        network_request.assert_not_called()
        cos_client.put_object.assert_not_called()

    @pytest.mark.parametrize("failure", ["domain", "client", "bucket", "put_object", "invalid_image"])
    def test_generate_icon_falls_back_for_invalid_image_but_not_cos_failures(self, monkeypatch, failure):
        app = Mock()
        app.config = {} if failure == "domain" else {"COS_DOMAIN": "https://test.cos.com"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", app)
        service = _build_service()
        cos_client = service.cos_service._get_client.return_value
        failure_call = {
            "client": service.cos_service._get_client,
            "bucket": service.cos_service._get_bucket,
            "put_object": cos_client.put_object,
        }.get(failure)
        if failure_call:
            failure_call.side_effect = RuntimeError("storage unavailable")
        response = _mock_image_response(_image_bytes("GIF" if failure == "invalid_image" else "PNG"))
        monkeypatch.setattr(
            "internal.service.icon_generator_service.safe_request", lambda *_args, **_kwargs: response
        )
        monkeypatch.setattr(
            service, "_generate_with_kolors",
            lambda *_a, **_kw: service._download_and_upload_image("https://example.com/icon.png", "kolors"),
        )
        qwen = Mock(return_value="https://qwen/icon.png")
        monkeypatch.setattr(service, "_generate_with_qwen", qwen)

        if failure == "invalid_image":
            assert service.generate_icon("app", "desc") == "https://qwen/icon.png"
            qwen.assert_called_once()
        else:
            with pytest.raises(IconStorageError):
                service.generate_icon("app", "desc")
            qwen.assert_not_called()

    def test_download_and_upload_image(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"COS_DOMAIN": "https://test.cos.com"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)
        monkeypatch.setattr(
            "internal.service.icon_generator_service.utc_now_naive",
            lambda: datetime(2026, 1, 2, 3, 4, 5),
        )

        mock_download_response = _mock_image_response(_image_bytes())

        with patch(
            "internal.service.icon_generator_service.safe_request",
            return_value=mock_download_response,
        ):
            mock_cos_client = Mock()
            mock_cos_service = SimpleNamespace(
                _get_client=Mock(return_value=mock_cos_client),
                _get_bucket=Mock(return_value="test-bucket"),
            )

            service = _build_service(cos_service=mock_cos_service)
            icon_url = service._download_and_upload_image("https://example.com/image.png", "test")

            assert icon_url.startswith("https://test.cos.com/")
            assert "2026/01/02/icons/" in icon_url
            assert "/icons/test_" in icon_url
            mock_cos_client.put_object.assert_called_once()

            call_args = mock_cos_client.put_object.call_args
            assert call_args[1]["Bucket"] == "test-bucket"
            assert call_args[1]["Body"].startswith(b"\x89PNG\r\n\x1a\n")
            assert call_args[1]["ContentType"] == "image/png"

    def test_download_and_upload_image_should_not_double_slash_cos_url(self, monkeypatch):
        app = Mock()
        app.config = {"COS_DOMAIN": "https://test.cos.com/"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", app)
        response = _mock_image_response(_image_bytes())
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *_a, **_kw: response)
        client = Mock()
        service = _build_service(cos_service=SimpleNamespace(
            _get_client=Mock(return_value=client),
            _get_bucket=Mock(return_value="bucket"),
        ))

        url = service._download_and_upload_image("https://example.com/icon.png", "test")

        assert url.startswith("https://test.cos.com/")
        assert not url.startswith("https://test.cos.com//")
        client.put_object.assert_called_once()

    def test_download_and_upload_image_should_raise_when_cos_domain_missing(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        mock_download_response = _mock_image_response(_image_bytes())
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *_args, **_kwargs: mock_download_response)

        mock_cos_service = SimpleNamespace(
            _get_client=Mock(return_value=Mock()),
            _get_bucket=Mock(return_value="bucket"),
        )
        service = _build_service(cos_service=mock_cos_service)

        with pytest.raises(FailException):
            service._download_and_upload_image("https://example.com/a.png", "kolors")

    def test_download_and_upload_image_should_normalize_supported_format_to_png(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"COS_DOMAIN": "https://test.cos.com"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)
        response = _mock_image_response(_image_bytes("JPEG"))
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *_args, **_kwargs: response)
        client = Mock()
        service = _build_service(cos_service=SimpleNamespace(
            _get_client=Mock(return_value=client),
            _get_bucket=Mock(return_value="test-bucket"),
        ))

        service._download_and_upload_image("https://example.com/image.jpg", "test")

        uploaded = client.put_object.call_args.kwargs
        assert uploaded["ContentType"] == "image/png"
        assert uploaded["Body"].startswith(b"\x89PNG\r\n\x1a\n")
        response.close.assert_called_once()

    def test_download_and_upload_image_should_reject_unsupported_format(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"COS_DOMAIN": "https://test.cos.com"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)
        response = _mock_image_response(_image_bytes("GIF"))
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *_args, **_kwargs: response)
        client = Mock()
        service = _build_service(cos_service=SimpleNamespace(
            _get_client=Mock(return_value=client),
            _get_bucket=Mock(return_value="test-bucket"),
        ))

        with pytest.raises(FailException, match="不支持的图片格式"):
            service._download_and_upload_image("https://example.com/image.gif", "test")

        client.put_object.assert_not_called()

    def test_download_and_upload_image_should_reject_malformed_image(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"COS_DOMAIN": "https://test.cos.com"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)
        response = _mock_image_response(b"not-an-image")
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *_args, **_kwargs: response)
        client = Mock()
        service = _build_service(cos_service=SimpleNamespace(
            _get_client=Mock(return_value=client),
            _get_bucket=Mock(return_value="test-bucket"),
        ))

        with pytest.raises(FailException, match="无效图片"):
            service._download_and_upload_image("https://example.com/image.png", "test")

        client.put_object.assert_not_called()

    def test_download_and_upload_image_should_reject_oversized_response(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"COS_DOMAIN": "https://test.cos.com"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)
        response = _mock_image_response(b"x" * (20 * 1024 * 1024 + 1))
        service = _build_service()

        with patch("internal.service.icon_generator_service.safe_request", return_value=response):
            with pytest.raises(FailException, match="超过大小限制"):
                service._download_and_upload_image("https://example.com/image.png", "test")

        response.close.assert_called_once()

    def test_download_and_upload_image_should_reject_invalid_content_length(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"COS_DOMAIN": "https://test.cos.com"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)
        response = _mock_image_response(_image_bytes())
        response.headers["Content-Length"] = "unknown"
        service = _build_service()

        with patch("internal.service.icon_generator_service.safe_request", return_value=response):
            with pytest.raises(FailException, match="响应长度无效"):
                service._download_and_upload_image("https://example.com/image.png", "test")

        response.close.assert_called_once()

    def test_download_and_upload_image_should_reject_negative_content_length(self, monkeypatch):
        app = Mock()
        app.config = {"COS_DOMAIN": "https://test.cos.com"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", app)
        response = _mock_image_response(_image_bytes())
        response.headers["Content-Length"] = "-1"
        service = _build_service()

        with patch("internal.service.icon_generator_service.safe_request", return_value=response):
            with pytest.raises(FailException, match="图标响应长度无效"):
                service._download_and_upload_image("https://example.com/image.png", "test")

        response.close.assert_called_once()

    def test_generate_with_kolors_should_raise_when_images_empty(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        mock_response = Mock()
        mock_response.json.return_value = {"images": []}
        mock_response.raise_for_status = Mock()
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *_args, **_kwargs: mock_response)

        service = _build_service()

        with pytest.raises(FailException, match="Kolors 返回的图片列表为空"):
            service._generate_with_kolors("测试应用", "desc")

    def test_kolors_skips_invalid_image_entries_before_valid_url(self, monkeypatch):
        app = Mock()
        app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", app)

        response = Mock()
        response.json.return_value = {
            "images": [
                None,
                {},
                {"url": 7},
                {"url": " "},
                {"url": "not a URL"},
                {"url": "https://cdn.example/icon.png"},
            ]
        }
        response.raise_for_status = Mock()
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *a, **kw: response)

        service = _build_service()
        upload = Mock(return_value="https://cos.example/icon.png")
        monkeypatch.setattr(service, "_download_and_upload_image", upload)

        assert service._generate_with_kolors("App", "description") == "https://cos.example/icon.png"
        upload.assert_called_once_with("https://cdn.example/icon.png", "kolors")

    def test_generate_with_kolors_should_raise_when_image_url_missing(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        mock_response = Mock()
        mock_response.json.return_value = {"images": [{}]}
        mock_response.raise_for_status = Mock()
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *_args, **_kwargs: mock_response)

        service = _build_service()

        with pytest.raises(FailException, match="Kolors 返回的图片URL为空"):
            service._generate_with_kolors("测试应用", "desc")

    def test_generate_with_qwen_should_raise_when_images_empty(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        mock_response = Mock()
        mock_response.json.return_value = {"images": []}
        mock_response.raise_for_status = Mock()
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *_args, **_kwargs: mock_response)

        service = _build_service()

        with pytest.raises(FailException, match="Qwen 返回的图片列表为空"):
            service._generate_with_qwen("测试应用", "desc")

    def test_generate_with_qwen_should_raise_when_image_url_missing(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        mock_response = Mock()
        mock_response.json.return_value = {"images": [{}]}
        mock_response.raise_for_status = Mock()
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *_args, **_kwargs: mock_response)

        service = _build_service()

        with pytest.raises(FailException, match="Qwen 返回的图片URL为空"):
            service._generate_with_qwen("测试应用", "desc")

    def test_http_error_preserves_provider_message_on_failing_response(self):
        response = requests.Response()
        response.status_code = 503
        response._content = b'{"error": {"message": "provider temporarily offline"}}'
        service = _build_service()

        with pytest.raises(FailException, match="provider temporarily offline"):
            service._raise_request_error(
                "Kolors", requests.exceptions.HTTPError("HTTP 503", response=response)
            )

    @pytest.mark.parametrize("status_code", [200, 400])
    def test_generate_icon_stops_fallback_on_safety_rejection(self, monkeypatch, caplog, status_code):
        app = Mock()
        app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", app)

        provider_response = Mock()
        provider_response.status_code = status_code
        provider_response.json.return_value = {
            "error": {
                "code": "DataInspectionFailed",
                "message": "ICON_PROMPT_SECRET",
            }
        }
        provider_response.text = '{"error":{"code":"DataInspectionFailed"}}'
        if status_code == 400:
            provider_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                "HTTP 400", response=provider_response
            )
        monkeypatch.setattr(
            "internal.service.icon_generator_service.safe_request",
            lambda *_args, **_kwargs: provider_response,
        )

        service = _build_service()
        qwen = Mock(return_value="https://qwen/icon.png")
        dalle = Mock(return_value="https://dalle/icon.png")
        monkeypatch.setattr(service, "_generate_with_qwen", qwen)
        monkeypatch.setattr(service, "_generate_with_dalle", dalle)

        with caplog.at_level(logging.INFO), pytest.raises(IconGenerationRejectedError) as error:
            service.generate_icon("app", "desc")

        assert error.value.error_class == "safety_rejected"
        assert "ICON_PROMPT_SECRET" not in str(error.value)
        assert "ICON_PROMPT_SECRET" not in caplog.text
        assert "error_class=safety_rejected fallback=stopped" in caplog.text
        qwen.assert_not_called()
        dalle.assert_not_called()

    def test_generate_icon_stops_fallback_on_structured_provider_safety_code(self, monkeypatch):
        service = _build_service()

        class ProviderError(Exception):
            code = "content_policy_violation"

        monkeypatch.setattr(
            service,
            "_generate_with_kolors",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(ProviderError("rejected")),
        )
        qwen = Mock(return_value="https://qwen/icon.png")
        monkeypatch.setattr(service, "_generate_with_qwen", qwen)

        with pytest.raises(IconGenerationRejectedError) as error:
            service.generate_icon("app", "desc")

        assert error.value.error_class == "safety_rejected"
        qwen.assert_not_called()

    @pytest.mark.parametrize("body,expected", [
        (b'{"error": "quota exceeded"}', "quota exceeded"),
        (b'{"message": "service is unavailable"}', "service is unavailable"),
    ])
    def test_http_error_preserves_string_or_top_level_provider_message(self, body, expected):
        response = requests.Response()
        response.status_code = 503
        response._content = body
        service = _build_service()

        with pytest.raises(FailException, match=expected):
            service._raise_request_error(
                "Kolors", requests.exceptions.HTTPError("HTTP 503", response=response)
            )

    def test_generate_with_kolors_should_raise_when_http_429(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        class _Response:
            status_code = 429

            @staticmethod
            def json():
                return {"error": {"message": "too many requests"}}

            def raise_for_status(self):
                raise requests.exceptions.HTTPError("too-many-requests", response=self)

        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *_args, **_kwargs: _Response())

        service = _build_service()

        with pytest.raises(FailException, match="请求过于频繁"):
            service._generate_with_kolors("测试应用", "desc")

    def test_kolors_rejects_provider_non_json_response(self, monkeypatch):
        app = Mock()
        app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", app)
        response = Mock()
        response.json.side_effect = ValueError("not valid JSON")
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *_a, **_k: response)
        service = _build_service()

        with pytest.raises(FailException, match="Kolors 返回的图片响应格式无效"):
            service._generate_with_kolors("Demo", "desc")

    @pytest.mark.parametrize("payload", [None, [], "unexpected response"])
    def test_kolors_rejects_invalid_provider_response_shape(self, monkeypatch, payload):
        app = Mock()
        app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", app)
        response = Mock()
        response.json.return_value = payload
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *a, **kw: response)
        service = _build_service()

        with pytest.raises(FailException, match="图片响应格式无效"):
            service._generate_with_kolors("App", "description")

    @pytest.mark.parametrize("images", [{"url": "https://cdn.example/icon.png"}, "unexpected", None, "", 0])
    def test_kolors_rejects_non_list_images(self, monkeypatch, images):
        app = Mock()
        app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", app)
        response = Mock()
        response.json.return_value = {"images": images}
        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", lambda *a, **kw: response)
        service = _build_service()

        with pytest.raises(FailException, match="图片列表格式无效"):
            service._generate_with_kolors("App", "description")

    @pytest.mark.parametrize("invalid_url", [" ", "file:///etc/passwd", "javascript:alert(1)", "not a url"])
    def test_dalle_rejects_non_http_image_urls_before_download(self, monkeypatch, invalid_url):
        app = Mock()
        app.config = {"OPENAI_API_KEY": "openai-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", app)
        service = _build_service()
        dalle = Mock()
        dalle.run.return_value = invalid_url
        monkeypatch.setattr("internal.service.icon_generator_service.DallEAPIWrapper", lambda **_kwargs: dalle)
        download = Mock()
        monkeypatch.setattr(service, "_download_and_upload_image", download)

        with pytest.raises(FailException, match="DALLE 返回的图片URL为空"):
            service._generate_with_dalle("Demo", "")

        download.assert_not_called()

    def test_generate_with_dalle_should_raise_when_image_url_empty(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"OPENAI_API_KEY": "openai-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        service = _build_service()

        mock_dalle = Mock()
        mock_dalle.run.return_value = ""
        monkeypatch.setattr("internal.service.icon_generator_service.DallEAPIWrapper", lambda **_kwargs: mock_dalle)

        with pytest.raises(FailException, match="DALLE 返回的图片URL为空"):
            service._generate_with_dalle("测试应用", "desc")

    def test_generate_icon_should_raise_when_all_providers_return_empty_url(self, monkeypatch):
        service = _build_service()
        monkeypatch.setattr(service, "_generate_with_kolors", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service, "_generate_with_qwen", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service, "_generate_with_dalle", lambda *_args, **_kwargs: None)

        with pytest.raises(FailException, match="图标生成服务暂时不可用"):
            service.generate_icon("测试应用", "desc")

    def test_generate_icon_should_try_providers_in_order_when_all_raise(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        service = _build_service()
        call_order = []

        def _raise_kolors(*_args, **_kwargs):
            call_order.append("kolors")
            raise FailException("kolors-error")

        def _raise_qwen(*_args, **_kwargs):
            call_order.append("qwen")
            raise FailException("qwen-error")

        def _raise_dalle(*_args, **_kwargs):
            call_order.append("dalle")
            raise FailException("dalle-error")

        monkeypatch.setattr(service, "_generate_with_kolors", _raise_kolors)
        monkeypatch.setattr(service, "_generate_with_qwen", _raise_qwen)
        monkeypatch.setattr(service, "_generate_with_dalle", _raise_dalle)

        with pytest.raises(FailException, match="图标生成服务暂时不可用"):
            service.generate_icon("测试应用", "desc")

        assert call_order == ["kolors", "qwen", "dalle"]

    def test_generate_icon_should_not_log_provider_exception_details(self, monkeypatch, caplog):
        mock_app = Mock()
        api_key = "SYNTHETIC_API_KEY"
        mock_app.config = {"SILICONFLOW_API_KEY": api_key, "OPENAI_API_KEY": api_key}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)
        service = _build_service()
        secret = "SYNTHETIC_PROVIDER_CREDENTIAL"
        failure = RuntimeError(f"provider response contains {secret}")
        monkeypatch.setattr(service, "_generate_with_kolors", lambda *_args: (_ for _ in ()).throw(failure))
        monkeypatch.setattr(service, "_generate_with_qwen", lambda *_args: (_ for _ in ()).throw(failure))
        monkeypatch.setattr(service, "_generate_with_dalle", lambda *_args: (_ for _ in ()).throw(failure))

        with caplog.at_level(logging.INFO), pytest.raises(FailException, match="图标生成服务暂时不可用"):
            service.generate_icon("ICON_USER_NAME_SECRET", "ICON_USER_DESCRIPTION_SECRET")

        assert secret not in caplog.text
        assert api_key not in caplog.text
        assert "provider=Kolors model=Kwai-Kolors/Kolors attempt=1 status=failed" in caplog.text
        assert "provider=Qwen model=Qwen/Qwen-Image attempt=2 status=failed" in caplog.text
        assert "provider=DALLE model=dall-e-3 attempt=3 status=failed" in caplog.text
        assert "error_class=provider_error" in caplog.text
        assert "error_class=all_providers_failed" in caplog.text
        assert "ICON_USER_NAME_SECRET" not in caplog.text
        assert "ICON_USER_DESCRIPTION_SECRET" not in caplog.text
        assert "A stable mocked icon prompt" not in caplog.text

    def test_generate_with_kolors_should_send_expected_request_payload(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {
            "SILICONFLOW_API_KEY": "sf-key",
            "SILICONFLOW_API_BASE": "https://api.example.com",
        }
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        request_snapshot = {}
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {"images": [{"url": "https://kolors.example/icon.png"}]}

        def _mock_safe_request(method, url, **kwargs):
            request_snapshot["method"] = method
            request_snapshot["url"] = url
            request_snapshot["json"] = kwargs.get("json")
            request_snapshot["headers"] = kwargs.get("headers")
            request_snapshot["timeout"] = kwargs.get("timeout")
            return response

        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", _mock_safe_request)

        service = _build_service()
        monkeypatch.setattr(
            service,
            "_download_and_upload_image",
            lambda image_url, source: f"https://cos/{source}?url={image_url}",
        )

        result = service._generate_with_kolors("测试应用", "desc")

        assert result == "https://cos/kolors?url=https://kolors.example/icon.png"
        assert request_snapshot["url"] == "https://api.example.com/v1/images/generations"
        assert request_snapshot["timeout"] == 60
        assert request_snapshot["headers"] == {
            "Authorization": "Bearer sf-key",
            "Content-Type": "application/json",
        }
        assert request_snapshot["json"] == {
            "model": "Kwai-Kolors/Kolors",
            "prompt": "A stable mocked icon prompt",
            "image_size": "1024x1024",
            "batch_size": 1,
            "num_inference_steps": 20,
            "guidance_scale": 7.5,
        }

    def test_generate_with_qwen_should_send_expected_request_payload(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {
            "SILICONFLOW_API_KEY": "sf-key",
            "SILICONFLOW_API_BASE": "https://api.example.com",
        }
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        request_snapshot = {}
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {"images": [{"url": "https://qwen.example/icon.png"}]}

        def _mock_safe_request(method, url, **kwargs):
            request_snapshot["method"] = method
            request_snapshot["url"] = url
            request_snapshot["json"] = kwargs.get("json")
            request_snapshot["headers"] = kwargs.get("headers")
            request_snapshot["timeout"] = kwargs.get("timeout")
            return response

        monkeypatch.setattr("internal.service.icon_generator_service.safe_request", _mock_safe_request)

        service = _build_service()
        monkeypatch.setattr(
            service,
            "_download_and_upload_image",
            lambda image_url, source: f"https://cos/{source}?url={image_url}",
        )

        result = service._generate_with_qwen("测试应用", "desc")

        assert result == "https://cos/qwen?url=https://qwen.example/icon.png"
        assert request_snapshot["url"] == "https://api.example.com/v1/images/generations"
        assert request_snapshot["timeout"] == 60
        assert request_snapshot["headers"] == {
            "Authorization": "Bearer sf-key",
            "Content-Type": "application/json",
        }
        assert request_snapshot["json"] == {
            "model": "Qwen/Qwen-Image",
            "prompt": "A stable mocked icon prompt",
            "image_size": "1328x1328",
            "num_inference_steps": 50,
            "cfg": 4.0,
        }

    def test_generate_with_dalle_should_construct_wrapper_with_expected_options(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"OPENAI_API_KEY": "openai-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        wrapper_kwargs = {}
        run_payload = {}

        class _FakeDalle:
            def __init__(self, **kwargs):
                wrapper_kwargs.update(kwargs)

            def run(self, prompt):
                run_payload["prompt"] = prompt
                return "https://dalle.example/icon.png"

        monkeypatch.setattr("internal.service.icon_generator_service.DallEAPIWrapper", _FakeDalle)

        service = _build_service()
        monkeypatch.setattr(
            service,
            "_download_and_upload_image",
            lambda image_url, source: f"https://cos/{source}?url={image_url}",
        )

        result = service._generate_with_dalle("测试应用", "desc")

        assert result == "https://cos/dalle?url=https://dalle.example/icon.png"
        assert wrapper_kwargs == {
            "model": "dall-e-3",
            "api_key": "openai-key",
            "size": "1024x1024",
            "quality": "standard",
            "n": 1,
        }
        assert run_payload["prompt"] == "A stable mocked icon prompt"
