from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

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
    """测试图标生成服务"""

    def test_generate_icon_with_kolors_success(self, monkeypatch):
        """测试使用 Kolors 成功生成图标"""
        # Mock Flask current_app
        mock_app = Mock()
        mock_app.config = {
            "SILICONFLOW_API_KEY": "test-key",
            "COS_DOMAIN": "https://test.cos.com"
        }
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        # Mock requests.post for Kolors API
        mock_response = Mock()
        mock_response.json.return_value = {
            "images": [{"url": "https://kolors.com/image.png"}]
        }
        mock_response.raise_for_status = Mock()

        # Mock requests.get for image download
        mock_download_response = Mock()
        mock_download_response.content = b"fake-image-data"
        mock_download_response.raise_for_status = Mock()

        with patch("internal.service.icon_generator_service.requests.post", return_value=mock_response):
            with patch("internal.service.icon_generator_service.requests.get", return_value=mock_download_response):
                # Mock COS client
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

    def test_generate_icon_fallback_to_qwen(self, monkeypatch):
        """测试 Kolors 失败后降级到 Qwen"""
        # Mock Flask current_app
        mock_app = Mock()
        mock_app.config = {
            "SILICONFLOW_API_KEY": None,  # Kolors 不可用
            "DASHSCOPE_API_KEY": "test-qwen-key",
            "COS_DOMAIN": "https://test.cos.com"
        }
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        # Mock Qwen API responses
        mock_submit_response = Mock()
        mock_submit_response.json.return_value = {
            "output": {"task_id": "test-task-id"}
        }
        mock_submit_response.raise_for_status = Mock()

        mock_task_response = Mock()
        mock_task_response.json.return_value = {
            "output": {
                "task_status": "SUCCEEDED",
                "results": [{"url": "https://qwen.com/image.png"}]
            }
        }
        mock_task_response.raise_for_status = Mock()

        # Mock image download
        mock_download_response = Mock()
        mock_download_response.content = b"fake-image-data"
        mock_download_response.raise_for_status = Mock()

        def mock_requests_post(url, *args, **kwargs):
            if "text2image" in url:
                return mock_submit_response
            return Mock()

        def mock_requests_get(url, *args, **kwargs):
            if "tasks" in url:
                return mock_task_response
            return mock_download_response

        with patch("internal.service.icon_generator_service.requests.post", side_effect=mock_requests_post):
            with patch("internal.service.icon_generator_service.requests.get", side_effect=mock_requests_get):
                # Mock COS client
                mock_cos_client = Mock()
                mock_cos_service = SimpleNamespace(
                    _get_client=Mock(return_value=mock_cos_client),
                    _get_bucket=Mock(return_value="test-bucket"),
                )

                service = _build_service(cos_service=mock_cos_service)
                icon_url = service.generate_icon("测试应用", "这是一个测试应用")

                assert icon_url.startswith("https://test.cos.com/")
                assert "/icons/qwen_" in icon_url

    def test_generate_icon_fallback_to_dalle(self, monkeypatch):
        """测试 Kolors 和 Qwen 都失败后降级到 DALLE"""
        # Mock Flask current_app
        mock_app = Mock()
        mock_app.config = {
            "SILICONFLOW_API_KEY": None,  # Kolors 不可用
            "DASHSCOPE_API_KEY": None,  # Qwen 不可用
            "OPENAI_API_KEY": "test-openai-key",
            "COS_DOMAIN": "https://test.cos.com"
        }
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        # Mock DALLE wrapper
        mock_dalle = Mock()
        mock_dalle.run.return_value = "https://dalle.com/image.png"

        # Mock image download
        mock_download_response = Mock()
        mock_download_response.content = b"fake-image-data"
        mock_download_response.raise_for_status = Mock()

        with patch("internal.service.icon_generator_service.DallEAPIWrapper", return_value=mock_dalle):
            with patch("internal.service.icon_generator_service.requests.get", return_value=mock_download_response):
                # Mock COS client
                mock_cos_client = Mock()
                mock_cos_service = SimpleNamespace(
                    _get_client=Mock(return_value=mock_cos_client),
                    _get_bucket=Mock(return_value="test-bucket"),
                )

                service = _build_service(cos_service=mock_cos_service)
                icon_url = service.generate_icon("测试应用", "这是一个测试应用")

                assert icon_url.startswith("https://test.cos.com/")
                assert "/icons/dalle_" in icon_url

    def test_generate_icon_all_services_fail(self, monkeypatch):
        """测试所有服务都失败时抛出异常"""
        # Mock Flask current_app
        mock_app = Mock()
        mock_app.config = {
            "SILICONFLOW_API_KEY": None,
            "DASHSCOPE_API_KEY": None,
            "OPENAI_API_KEY": None,
        }
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        service = _build_service()

        with pytest.raises(FailException) as exc_info:
            service.generate_icon("测试应用", "这是一个测试应用")

        assert "图标生成服务暂时不可用" in str(exc_info.value)

    def test_generate_icon_prompt_generation(self, monkeypatch):
        """测试图标提示词生成"""
        # Mock Flask current_app
        mock_app = Mock()
        mock_app.config = {
            "SILICONFLOW_API_KEY": "test-key",
            "COS_DOMAIN": "https://test.cos.com"
        }
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        # Mock LLM
        mock_llm = Mock()
        mock_chain = Mock()
        mock_chain.invoke.return_value = "A beautiful icon for test app"

        with patch("internal.service.icon_generator_service.ChatPromptTemplate") as mock_template:
            mock_template.from_template.return_value.__or__ = Mock(
                return_value=Mock(__or__=Mock(return_value=mock_chain))
            )

            mock_language_model_manager = SimpleNamespace(
                get_default_model=Mock(return_value=mock_llm)
            )

            service = _build_service(language_model_manager=mock_language_model_manager)

            # Mock the rest of the flow
            with patch.object(service, "_generate_with_kolors", return_value="https://test.cos.com/icon.png"):
                icon_url = service.generate_icon("测试应用", "这是一个测试应用")
                assert icon_url == "https://test.cos.com/icon.png"

    def test_download_and_upload_image(self, monkeypatch):
        """测试下载图片并上传到 COS"""
        # Mock Flask current_app
        mock_app = Mock()
        mock_app.config = {
            "COS_DOMAIN": "https://test.cos.com"
        }
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        # Mock image download
        mock_download_response = Mock()
        mock_download_response.content = b"fake-image-data"
        mock_download_response.raise_for_status = Mock()

        with patch("internal.service.icon_generator_service.requests.get", return_value=mock_download_response):
            # Mock COS client
            mock_cos_client = Mock()
            mock_cos_service = SimpleNamespace(
                _get_client=Mock(return_value=mock_cos_client),
                _get_bucket=Mock(return_value="test-bucket"),
            )

            service = _build_service(cos_service=mock_cos_service)
            icon_url = service._download_and_upload_image("https://example.com/image.png", "test")

            assert icon_url.startswith("https://test.cos.com/")
            assert "/icons/test_" in icon_url
            mock_cos_client.put_object.assert_called_once()

            # Verify the call arguments
            call_args = mock_cos_client.put_object.call_args
            assert call_args[1]["Bucket"] == "test-bucket"
            assert call_args[1]["Body"] == b"fake-image-data"
            assert call_args[1]["ContentType"] == "image/png"

    def test_generate_icon_should_fallback_when_kolors_returns_none(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        service = _build_service()
        monkeypatch.setattr(service, "_generate_with_kolors", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service, "_generate_with_qwen", lambda *_args, **_kwargs: "https://qwen/icon.png")

        icon_url = service.generate_icon("测试应用", "desc")

        assert icon_url == "https://qwen/icon.png"

    def test_generate_icon_prompt_should_append_style_suffix_when_llm_succeeds(self, monkeypatch):
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
                return "A polished business logo"

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

        assert prompt.startswith("A polished business logo")
        assert "simple icon design" in prompt
        assert "flat style" in prompt

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

        assert prompt == "A simple and clean icon for 测试应用 application, flat design, minimalist style"

    def test_generate_with_kolors_should_raise_when_images_empty(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"SILICONFLOW_API_KEY": "test-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        mock_response = Mock()
        mock_response.json.return_value = {"images": []}
        mock_response.raise_for_status = Mock()
        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", lambda *_args, **_kwargs: mock_response)

        service = _build_service()
        monkeypatch.setattr(service, "_generate_icon_prompt", lambda *_args, **_kwargs: "prompt")

        with pytest.raises(FailException):
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
        monkeypatch.setattr(service, "_generate_icon_prompt", lambda *_args, **_kwargs: "prompt")

        with pytest.raises(FailException):
            service._generate_with_kolors("测试应用", "desc")

    def test_generate_with_qwen_should_raise_when_task_id_missing(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"DASHSCOPE_API_KEY": "qwen-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        submit_response = Mock()
        submit_response.json.return_value = {"output": {}}
        submit_response.raise_for_status = Mock()
        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", lambda *_args, **_kwargs: submit_response)

        service = _build_service()
        monkeypatch.setattr(service, "_generate_icon_prompt", lambda *_args, **_kwargs: "prompt")

        with pytest.raises(FailException):
            service._generate_with_qwen("测试应用", "desc")

    def test_generate_with_qwen_should_raise_when_succeeded_but_url_missing(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"DASHSCOPE_API_KEY": "qwen-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        submit_response = Mock()
        submit_response.json.return_value = {"output": {"task_id": "task-1"}}
        submit_response.raise_for_status = Mock()
        task_response = Mock()
        task_response.json.return_value = {
            "output": {"task_status": "SUCCEEDED", "results": [{}]}
        }
        task_response.raise_for_status = Mock()

        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", lambda *_args, **_kwargs: submit_response)
        monkeypatch.setattr("internal.service.icon_generator_service.requests.get", lambda *_args, **_kwargs: task_response)
        monkeypatch.setattr("time.sleep", lambda _sec: None)

        service = _build_service()
        monkeypatch.setattr(service, "_generate_icon_prompt", lambda *_args, **_kwargs: "prompt")

        with pytest.raises(FailException):
            service._generate_with_qwen("测试应用", "desc")

    def test_generate_with_qwen_should_raise_when_succeeded_but_results_empty(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"DASHSCOPE_API_KEY": "qwen-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        submit_response = Mock()
        submit_response.json.return_value = {"output": {"task_id": "task-1"}}
        submit_response.raise_for_status = Mock()
        task_response = Mock()
        task_response.json.return_value = {
            "output": {"task_status": "SUCCEEDED", "results": []}
        }
        task_response.raise_for_status = Mock()

        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", lambda *_args, **_kwargs: submit_response)
        monkeypatch.setattr("internal.service.icon_generator_service.requests.get", lambda *_args, **_kwargs: task_response)
        monkeypatch.setattr("time.sleep", lambda _sec: None)

        service = _build_service()
        monkeypatch.setattr(service, "_generate_icon_prompt", lambda *_args, **_kwargs: "prompt")

        with pytest.raises(FailException):
            service._generate_with_qwen("测试应用", "desc")

    def test_generate_with_qwen_should_raise_when_task_failed(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"DASHSCOPE_API_KEY": "qwen-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        submit_response = Mock()
        submit_response.json.return_value = {"output": {"task_id": "task-2"}}
        submit_response.raise_for_status = Mock()
        task_response = Mock()
        task_response.json.return_value = {
            "output": {"task_status": "FAILED", "message": "bad prompt"}
        }
        task_response.raise_for_status = Mock()

        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", lambda *_args, **_kwargs: submit_response)
        monkeypatch.setattr("internal.service.icon_generator_service.requests.get", lambda *_args, **_kwargs: task_response)
        monkeypatch.setattr("time.sleep", lambda _sec: None)

        service = _build_service()
        monkeypatch.setattr(service, "_generate_icon_prompt", lambda *_args, **_kwargs: "prompt")

        with pytest.raises(FailException):
            service._generate_with_qwen("测试应用", "desc")

    def test_generate_with_qwen_should_raise_when_task_timeout(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"DASHSCOPE_API_KEY": "qwen-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        submit_response = Mock()
        submit_response.json.return_value = {"output": {"task_id": "task-3"}}
        submit_response.raise_for_status = Mock()
        running_response = Mock()
        running_response.json.return_value = {"output": {"task_status": "RUNNING"}}
        running_response.raise_for_status = Mock()

        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", lambda *_args, **_kwargs: submit_response)
        monkeypatch.setattr("internal.service.icon_generator_service.requests.get", lambda *_args, **_kwargs: running_response)
        monkeypatch.setattr("time.sleep", lambda _sec: None)

        service = _build_service()
        monkeypatch.setattr(service, "_generate_icon_prompt", lambda *_args, **_kwargs: "prompt")

        with pytest.raises(FailException):
            service._generate_with_qwen("测试应用", "desc")

    def test_generate_with_dalle_should_raise_when_image_url_empty(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"OPENAI_API_KEY": "openai-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        service = _build_service()
        monkeypatch.setattr(service, "_generate_icon_prompt", lambda *_args, **_kwargs: "prompt")

        mock_dalle = Mock()
        mock_dalle.run.return_value = ""
        monkeypatch.setattr("internal.service.icon_generator_service.DallEAPIWrapper", lambda **_kwargs: mock_dalle)

        with pytest.raises(FailException):
            service._generate_with_dalle("测试应用", "desc")

    def test_generate_icon_should_raise_when_all_providers_return_empty_url(self, monkeypatch):
        service = _build_service()
        monkeypatch.setattr(service, "_generate_with_kolors", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service, "_generate_with_qwen", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service, "_generate_with_dalle", lambda *_args, **_kwargs: None)

        with pytest.raises(FailException, match="图标生成服务暂时不可用"):
            service.generate_icon("测试应用", "desc")

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

    def test_generate_icon_should_fallback_to_dalle_when_qwen_returns_none(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        service = _build_service()

        def _raise_kolors(*_args, **_kwargs):
            raise FailException("kolors failed")

        monkeypatch.setattr(service, "_generate_with_kolors", _raise_kolors)
        monkeypatch.setattr(service, "_generate_with_qwen", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service, "_generate_with_dalle", lambda *_args, **_kwargs: "https://dalle/icon.png")

        icon_url = service.generate_icon("测试应用", "desc")

        assert icon_url == "https://dalle/icon.png"

    def test_generate_icon_should_raise_when_all_services_return_none(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        service = _build_service()
        monkeypatch.setattr(service, "_generate_with_kolors", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service, "_generate_with_qwen", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service, "_generate_with_dalle", lambda *_args, **_kwargs: None)

        with pytest.raises(FailException):
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
        mock_app.config = {"SILICONFLOW_API_KEY": "sf-key"}
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
        monkeypatch.setattr(service, "_generate_icon_prompt", lambda *_args, **_kwargs: "ICON-PROMPT")
        monkeypatch.setattr(
            service,
            "_download_and_upload_image",
            lambda image_url, source: f"https://cos/{source}?url={image_url}",
        )

        result = service._generate_with_kolors("测试应用", "desc")

        assert result == "https://cos/kolors?url=https://kolors.example/icon.png"
        assert request_snapshot["url"] == "https://api.siliconflow.cn/v1/images/generations"
        assert request_snapshot["timeout"] == 60
        assert request_snapshot["headers"] == {
            "Authorization": "Bearer sf-key",
            "Content-Type": "application/json",
        }
        assert request_snapshot["json"] == {
            "model": "black-forest-labs/FLUX.1-schnell",
            "prompt": "ICON-PROMPT",
            "image_size": "512x512",
            "num_inference_steps": 4,
        }

    def test_generate_with_qwen_should_poll_task_and_use_expected_auth_header(self, monkeypatch):
        mock_app = Mock()
        mock_app.config = {"DASHSCOPE_API_KEY": "dash-key"}
        monkeypatch.setattr("internal.service.icon_generator_service.current_app", mock_app)

        post_snapshot = {}
        get_snapshots = []

        submit_response = Mock()
        submit_response.raise_for_status = Mock()
        submit_response.json.return_value = {"output": {"task_id": "task-xyz"}}

        running_response = Mock()
        running_response.raise_for_status = Mock()
        running_response.json.return_value = {"output": {"task_status": "RUNNING"}}

        succeeded_response = Mock()
        succeeded_response.raise_for_status = Mock()
        succeeded_response.json.return_value = {
            "output": {
                "task_status": "SUCCEEDED",
                "results": [{"url": "https://qwen.example/icon.png"}],
            }
        }

        get_queue = [running_response, succeeded_response]

        def _mock_post(url, *args, **kwargs):
            post_snapshot["url"] = url
            post_snapshot["json"] = kwargs.get("json")
            post_snapshot["headers"] = kwargs.get("headers")
            post_snapshot["timeout"] = kwargs.get("timeout")
            return submit_response

        def _mock_get(url, *args, **kwargs):
            get_snapshots.append({
                "url": url,
                "headers": kwargs.get("headers"),
                "timeout": kwargs.get("timeout"),
            })
            return get_queue.pop(0)

        monkeypatch.setattr("internal.service.icon_generator_service.requests.post", _mock_post)
        monkeypatch.setattr("internal.service.icon_generator_service.requests.get", _mock_get)
        monkeypatch.setattr("time.sleep", lambda _sec: None)

        service = _build_service()
        monkeypatch.setattr(service, "_generate_icon_prompt", lambda *_args, **_kwargs: "ICON-PROMPT")
        monkeypatch.setattr(
            service,
            "_download_and_upload_image",
            lambda image_url, source: f"https://cos/{source}?url={image_url}",
        )

        result = service._generate_with_qwen("测试应用", "desc")

        assert result == "https://cos/qwen?url=https://qwen.example/icon.png"
        assert post_snapshot["url"] == "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
        assert post_snapshot["timeout"] == 30
        assert post_snapshot["headers"] == {
            "X-DashScope-Async": "enable",
            "Authorization": "Bearer dash-key",
            "Content-Type": "application/json",
        }
        assert post_snapshot["json"] == {
            "model": "wanx-v1",
            "input": {"prompt": "ICON-PROMPT"},
            "parameters": {"size": "1024*1024", "n": 1},
        }

        assert len(get_snapshots) == 2
        assert get_snapshots[0]["url"] == "https://dashscope.aliyuncs.com/api/v1/tasks/task-xyz"
        assert get_snapshots[0]["headers"] == {"Authorization": "Bearer dash-key"}
        assert get_snapshots[0]["timeout"] == 10

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
        monkeypatch.setattr(service, "_generate_icon_prompt", lambda *_args, **_kwargs: "ICON-PROMPT")
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
        assert run_payload["prompt"] == "ICON-PROMPT"
