from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from internal.exception import FailException
from internal.service.icon_generator_service import IconGeneratorService

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

        mock_download_response = Mock()
        mock_download_response.content = b"fake-image-data"
        mock_download_response.raise_for_status = Mock()

        with patch("internal.service.icon_generator_service.requests.post", return_value=mock_response):
            with patch("internal.service.icon_generator_service.requests.get", return_value=mock_download_response):
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

    def test_generate_icon_should_fallback_to_qwen_when_kolors_rate_limited(self, monkeypatch):
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

        icon_url = service.generate_icon("测试应用", "desc")

        assert icon_url == "https://qwen/icon.png"

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

    def test_generate_icon_prompt_should_fallback_to_default_when_llm_raises(self, monkeypatch):
        monkeypatch.setattr(
            IconGeneratorService,
            "_generate_icon_prompt",
            _ORIGINAL_GENERATE_ICON_PROMPT,
        )

        def _raise_template_error(_template):
            raise RuntimeError("prompt-generation-failed")

        monkeypatch.setattr(
            "internal.service.icon_generator_service.ChatPromptTemplate.from_template",
            _raise_template_error,
        )

        service = _build_service()
        prompt = service._generate_icon_prompt("测试应用", "desc")

        assert "mobile app launcher icon" in prompt
        assert "rounded square app icon composition" in prompt
        assert "no text, no watermark, no extra elements" in prompt

    def test_download_and_upload_image(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"COS_DOMAIN": "https://test.cos.com"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)
        monkeypatch.setattr(
            "internal.service.icon_generator_service.utc_now_naive",
            lambda: datetime(2026, 1, 2, 3, 4, 5),
        )

        mock_download_response = Mock()
        mock_download_response.content = b"fake-image-data"
        mock_download_response.raise_for_status = Mock()

        with patch("internal.service.icon_generator_service.requests.get", return_value=mock_download_response):
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
            assert call_args[1]["Body"] == b"fake-image-data"
            assert call_args[1]["ContentType"] == "image/png"

    def test_download_and_upload_image_should_raise_when_cos_domain_missing(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        mock_download_response = Mock()
        mock_download_response.content = b"image"
        mock_download_response.raise_for_status = Mock()
        monkeypatch.setattr("internal.service.icon_generator_service.requests.get", lambda *_args, **_kwargs: mock_download_response)

        mock_cos_service = SimpleNamespace(
            _get_client=Mock(return_value=Mock()),
            _get_bucket=Mock(return_value="bucket"),
        )
        service = _build_service(cos_service=mock_cos_service)

        with pytest.raises(FailException):
            service._download_and_upload_image("https://example.com/a.png", "kolors")

    def test_generate_with_kolors_should_raise_when_images_empty(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        mock_response = Mock()
        mock_response.json.return_value = {"images": []}
        mock_response.raise_for_status = Mock()
        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", lambda *_args, **_kwargs: mock_response)

        service = _build_service()

        with pytest.raises(FailException, match="Kolors 返回的图片列表为空"):
            service._generate_with_kolors("测试应用", "desc")

    def test_generate_with_kolors_should_raise_when_image_url_missing(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        mock_response = Mock()
        mock_response.json.return_value = {"images": [{}]}
        mock_response.raise_for_status = Mock()
        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", lambda *_args, **_kwargs: mock_response)

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
        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", lambda *_args, **_kwargs: mock_response)

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
        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", lambda *_args, **_kwargs: mock_response)

        service = _build_service()

        with pytest.raises(FailException, match="Qwen 返回的图片URL为空"):
            service._generate_with_qwen("测试应用", "desc")

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

        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", lambda *_args, **_kwargs: _Response())

        service = _build_service()

        with pytest.raises(FailException, match="请求过于频繁"):
            service._generate_with_kolors("测试应用", "desc")

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

        def _mock_post(url, *args, **kwargs):
            request_snapshot["url"] = url
            request_snapshot["json"] = kwargs.get("json")
            request_snapshot["headers"] = kwargs.get("headers")
            request_snapshot["timeout"] = kwargs.get("timeout")
            return response

        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", _mock_post)

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

        def _mock_post(url, *args, **kwargs):
            request_snapshot["url"] = url
            request_snapshot["json"] = kwargs.get("json")
            request_snapshot["headers"] = kwargs.get("headers")
            request_snapshot["timeout"] = kwargs.get("timeout")
            return response

        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", _mock_post)

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
