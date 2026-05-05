from types import SimpleNamespace
from pathlib import Path

import pytest
import yaml

from internal.core.language_model.entities.model_entity import (
    BaseLanguageModel,
    ModelFeature,
    ModelType,
)
from internal.core.language_model.entities.provider_entity import (
    Provider,
    ProviderEntity,
)
from internal.core.language_model.language_model_manager import LanguageModelManager
from internal.core.language_model.providers.grok.chat import Chat as GrokChat
from internal.core.language_model.providers.moonshot.chat import Chat as MoonshotChat
from internal.core.language_model.providers.tongyi.chat import Chat as TongyiChat
from internal.core.language_model.providers.wenxin.chat import Chat as WenxinChat
from internal.exception import FailException, NotFoundException


def test_base_language_model_helpers_should_handle_pricing_and_multimodal_payload():
    dummy = SimpleNamespace(
        metadata={"pricing": {"input": 0.1, "output": 0.2, "unit": 1000}},
        features=[],
    )

    assert BaseLanguageModel.get_pricing(dummy) == (0.1, 0.2, 1000)
    assert (
        BaseLanguageModel.convert_to_human_message(
            dummy, "hello", ["https://img/1"]
        ).content
        == "hello"
    )

    dummy.features = [ModelFeature.IMAGE_INPUT.value]
    message = BaseLanguageModel.convert_to_human_message(
        dummy, "hello", ["https://img/1"]
    )
    assert message.content[0] == {"type": "text", "text": "hello"}
    assert message.content[1] == {
        "type": "image_url",
        "image_url": {"url": "https://img/1"},
    }


def test_provider_should_load_model_entities_and_expand_template_parameters(
    monkeypatch, tmp_path
):
    provider_root = tmp_path / "providers" / "demo"
    provider_root.mkdir(parents=True)
    (provider_root / "positions.yaml").write_text(
        yaml.safe_dump(["demo-chat"]), encoding="utf-8"
    )
    (provider_root / "demo-chat.yaml").write_text(
        yaml.safe_dump(
            {
                "model": "demo-chat",
                "label": "Demo Chat",
                "model_type": "chat",
                "context_window": 8192,
                "max_output_tokens": 1024,
                "parameters": [
                    {
                        "name": "temperature",
                        "use_template": "temperature",
                        "required": True,
                    },
                    {
                        "name": "custom_flag",
                        "label": "Custom Flag",
                        "type": "boolean",
                        "required": False,
                    },
                ],
                "metadata": {"pricing": {"input": 1.0, "output": 2.0, "unit": 1000}},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "internal.core.language_model.entities.provider_entity.os.path.abspath",
        lambda _path: str(tmp_path / "entities" / "provider_entity.py"),
    )
    monkeypatch.setattr(
        "internal.core.language_model.entities.provider_entity.dynamic_import",
        lambda module, symbol: f"{module}:{symbol}",
    )

    provider = Provider(
        name="demo",
        position=1,
        provider_entity=ProviderEntity(
            name="demo",
            label="Demo",
            description="demo provider",
            icon="icon.svg",
            background="#fff",
            supported_model_types=[ModelType.CHAT],
        ),
    )

    assert provider.get_model_class(ModelType.CHAT).endswith(":Chat")
    assert provider.get_model_entity("demo-chat").model_name == "demo-chat"
    assert len(provider.get_model_entities()) == 1
    # 这里断言模板字段被补全，确保 use_template 分支被执行。
    assert provider.get_model_entity("demo-chat").parameters[0].help != ""

    with pytest.raises(NotFoundException, match="模型类不存在"):
        provider.get_model_class(ModelType.COMPLETION)
    with pytest.raises(NotFoundException, match="模型实体不存在"):
        provider.get_model_entity("missing")


def test_provider_should_raise_when_positions_yaml_is_not_list(monkeypatch, tmp_path):
    provider_root = tmp_path / "providers" / "demo"
    provider_root.mkdir(parents=True)
    (provider_root / "positions.yaml").write_text(
        yaml.safe_dump({"bad": "shape"}), encoding="utf-8"
    )

    monkeypatch.setattr(
        "internal.core.language_model.entities.provider_entity.os.path.abspath",
        lambda _path: str(tmp_path / "entities" / "provider_entity.py"),
    )
    monkeypatch.setattr(
        "internal.core.language_model.entities.provider_entity.dynamic_import",
        lambda module, symbol: f"{module}:{symbol}",
    )

    with pytest.raises(FailException, match="positions.yaml数据格式错误"):
        Provider(
            name="demo",
            position=1,
            provider_entity=ProviderEntity(
                name="demo",
                label="Demo",
                description="demo provider",
                icon="icon.svg",
                background="#fff",
                supported_model_types=[ModelType.CHAT],
            ),
        )


def test_deepseek_provider_should_expose_latest_models(monkeypatch):
    repo_root = Path(__file__).resolve().parents[5]
    provider_entity_path = repo_root / "api/internal/core/language_model/entities/provider_entity.py"

    monkeypatch.setattr(
        "internal.core.language_model.entities.provider_entity.os.path.abspath",
        lambda _path: str(provider_entity_path),
    )
    monkeypatch.setattr(
        "internal.core.language_model.entities.provider_entity.dynamic_import",
        lambda module, symbol: f"{module}:{symbol}",
    )

    provider = Provider(
        name="deepseek",
        position=1,
        provider_entity=ProviderEntity(
            name="deepseek",
            label="DeepSeek",
            description="DeepSeek provider",
            icon="icon.png",
            background="#FFFFFF",
            supported_model_types=[ModelType.CHAT],
        ),
    )

    model_names = [model.model_name for model in provider.get_model_entities()]
    assert model_names[:2] == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert "deepseek-reasoner" in model_names
    assert "deepseek-chat" in model_names

    flash = provider.get_model_entity("deepseek-v4-flash")
    pro = provider.get_model_entity("deepseek-v4-pro")
    assert flash.context_window == 1_000_000
    assert flash.max_output_tokens == 384_000
    assert flash.attributes["model"] == "deepseek-v4-flash"
    assert pro.context_window == 1_000_000
    assert pro.max_output_tokens == 384_000
    assert pro.attributes["model"] == "deepseek-v4-pro"


def test_provider_pricing_should_be_rmb_across_all_models():
    repo_root = Path(__file__).resolve().parents[5]
    providers_root = repo_root / "api/internal/core/language_model/providers"

    def assert_all_currency_fields_are_rmb(node, rel_path: str):
        if isinstance(node, dict):
            if "currency" in node:
                assert node["currency"] == "RMB", f"{rel_path} has non-RMB currency {node['currency']}"
            for key, value in node.items():
                assert_all_currency_fields_are_rmb(value, f"{rel_path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                assert_all_currency_fields_are_rmb(value, f"{rel_path}[{index}]")

    for yaml_path in providers_root.rglob("*.yaml"):
        if yaml_path.name in {"providers.yaml", "positions.yaml"}:
            continue

        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue

        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            assert_all_currency_fields_are_rmb(
                metadata, yaml_path.relative_to(providers_root).as_posix()
            )

    deepseek_v4_pro = yaml.safe_load(
        (providers_root / "deepseek/deepseek-v4-pro.yaml").read_text(encoding="utf-8")
    )
    assert deepseek_v4_pro["metadata"]["pricing"]["currency"] == "RMB"
    assert deepseek_v4_pro["metadata"]["pricing"]["input"] == pytest.approx(0.000992)
    assert deepseek_v4_pro["metadata"]["pricing"]["output"] == pytest.approx(0.00595)
    assert deepseek_v4_pro["metadata"]["pricing_cache_hit"]["input"] == pytest.approx(
        0.000248
    )
    assert deepseek_v4_pro["metadata"]["pricing_cache_hit"]["output"] == pytest.approx(
        0.00595
    )

    gemini_pro = yaml.safe_load(
        (providers_root / "google/gemini-2.5-pro.yaml").read_text(encoding="utf-8")
    )
    assert gemini_pro["metadata"]["pricing"]["currency"] == "RMB"
    assert gemini_pro["metadata"]["pricing"]["input"] == pytest.approx(0.008548)
    assert gemini_pro["metadata"]["pricing"]["output"] == pytest.approx(0.068386)
    assert gemini_pro["metadata"]["pricing_tiered"]["long_context"]["currency"] == "RMB"
    assert gemini_pro["metadata"]["pricing_tiered"]["long_context"]["input"] == pytest.approx(
        0.017097
    )
    assert gemini_pro["metadata"]["pricing_tiered"]["long_context"]["output"] == pytest.approx(
        0.102579
    )

    grok_4 = yaml.safe_load((providers_root / "grok/grok-4.yaml").read_text(encoding="utf-8"))
    assert grok_4["metadata"]["pricing"]["currency"] == "RMB"
    assert grok_4["metadata"]["pricing"]["input"] == pytest.approx(0.020516)
    assert grok_4["metadata"]["pricing"]["output"] == pytest.approx(0.102579)
    assert grok_4["metadata"]["pricing_long_context"]["currency"] == "RMB"
    assert grok_4["metadata"]["pricing_long_context"]["input"] == pytest.approx(0.041032)
    assert grok_4["metadata"]["pricing_long_context"]["output"] == pytest.approx(0.205158)
    assert grok_4["metadata"]["pricing_cache_hit"]["currency"] == "RMB"
    assert grok_4["metadata"]["pricing_cache_hit"]["input"] == pytest.approx(0.005129)
    assert grok_4["metadata"]["pricing_cache_hit"]["output"] == pytest.approx(0.102579)

    gpt_5_2_pro = yaml.safe_load(
        (providers_root / "openai/gpt-5.2-pro.yaml").read_text(encoding="utf-8")
    )
    assert gpt_5_2_pro["metadata"]["pricing"]["currency"] == "RMB"
    assert gpt_5_2_pro["metadata"]["pricing"]["input"] == pytest.approx(0.136772)
    assert gpt_5_2_pro["metadata"]["pricing"]["output"] == pytest.approx(0.547089)

    glm_5 = yaml.safe_load((providers_root / "zhipu/glm-5.yaml").read_text(encoding="utf-8"))
    assert glm_5["metadata"]["pricing"]["currency"] == "RMB"
    assert glm_5["metadata"]["pricing"]["input"] == pytest.approx(0.004103)
    assert glm_5["metadata"]["pricing"]["output"] == pytest.approx(0.015045)


def test_language_model_manager_should_load_and_delegate(monkeypatch, tmp_path):
    providers_dir = tmp_path / "providers"
    providers_dir.mkdir()
    (providers_dir / "providers.yaml").write_text(
        yaml.safe_dump(
            [
                {
                    "name": "alpha",
                    "label": "Alpha",
                    "description": "alpha provider",
                    "icon": "a.svg",
                    "background": "#111",
                    "supported_model_types": ["chat"],
                },
                {
                    "name": "beta",
                    "label": "Beta",
                    "description": "beta provider",
                    "icon": "b.svg",
                    "background": "#222",
                    "supported_model_types": ["completion"],
                },
            ],
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    class _FakeProvider:
        def __init__(self, name, position, provider_entity):
            self.name = name
            self.position = position
            self.provider_entity = provider_entity

        @staticmethod
        def get_model_class(model_type):
            return f"class:{model_type}"

        @staticmethod
        def get_model_entity(_model_name):
            return SimpleNamespace(model_type=ModelType.CHAT)

    monkeypatch.setattr(
        "internal.core.language_model.language_model_manager.os.path.abspath",
        lambda _path: str(tmp_path / "language_model_manager.py"),
    )
    monkeypatch.setattr(
        "internal.core.language_model.language_model_manager.Provider", _FakeProvider
    )

    manager = LanguageModelManager()

    assert [provider.name for provider in manager.get_providers()] == ["alpha", "beta"]
    assert manager.get_provider("alpha").position == 1

    with pytest.raises(NotFoundException, match="服务提供商不存在"):
        manager.get_provider("missing")


def test_grok_env_resolver_should_apply_priority(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "")
    monkeypatch.setenv("XAI_API_KEY", "xkey")
    monkeypatch.delenv("GROK_API_BASE", raising=False)
    monkeypatch.delenv("XAI_API_BASE", raising=False)
    grok_resolved = GrokChat.resolve_grok_env({"model": "grok"})
    assert grok_resolved["api_key"] == "xkey"
    assert grok_resolved["base_url"] == "https://api.x.ai/v1"

    explicit = GrokChat.resolve_grok_env(
        {"api_key": "explicit", "base_url": "https://custom"}
    )
    assert explicit["api_key"] == "explicit"
    assert explicit["base_url"] == "https://custom"
    assert GrokChat.resolve_grok_env("raw-values") == "raw-values"

    # 覆盖 grok 的“openai_* 显式参数存在时不覆盖”分支。
    grok_openai = GrokChat.resolve_grok_env(
        {"openai_api_key": "ok", "openai_api_base": "obase"}
    )
    assert "api_key" not in grok_openai
    assert "base_url" not in grok_openai

    # 覆盖 grok 无 key 环境时不注入 api_key 的分支（28->31）。
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("GROK_API_BASE", "https://grok-base")
    grok_no_key = GrokChat.resolve_grok_env({"model": "grok"})
    assert "api_key" not in grok_no_key
    assert grok_no_key["base_url"] == "https://grok-base"

    # 覆盖 grok 中 `if base:` 的 False 分支（37->40）。
    class _FlipBool:
        def __init__(self):
            self.calls = 0

        def __bool__(self):
            self.calls += 1
            # 第一次用于 `or` 表达式时返回 True，第二次用于 `if base:` 时返回 False。
            return self.calls == 1

    flip = _FlipBool()

    def _fake_getenv(key, default=""):
        if key == "GROK_API_BASE":
            return flip
        return ""

    monkeypatch.setattr(
        "internal.core.language_model.providers.grok.chat.os.getenv", _fake_getenv
    )
    grok_flip = GrokChat.resolve_grok_env({"model": "grok"})
    assert "base_url" not in grok_flip


def test_tongyi_and_wenxin_default_params_should_merge_extension_fields(monkeypatch):
    monkeypatch.setattr(
        "langchain_community.chat_models.tongyi.ChatTongyi._default_params",
        property(lambda _self: {"base": True}),
    )
    monkeypatch.setattr(
        "langchain_community.chat_models.baidu_qianfan_endpoint.QianfanChatEndpoint._default_params",
        property(lambda _self: {"base": True}),
    )

    tongyi = TongyiChat.model_construct(
        temperature=0.5,
        max_tokens=128,
        presence_penalty=0.2,
        frequency_penalty=0.1,
        enable_search=True,
    )
    params = tongyi._default_params
    assert params["temperature"] == 0.5
    assert params["max_tokens"] == 128
    assert params["presence_penalty"] == 0.2
    assert params["frequency_penalty"] == 0.1
    assert params["enable_search"] is True

    wenxin = WenxinChat.model_construct(max_output_tokens=512, disable_search=True)
    wenxin_params = wenxin._default_params
    assert wenxin_params["max_output_tokens"] == 512
    assert wenxin_params["disable_search"] is True

    # 覆盖所有扩展字段为 None 时的分支（不追加参数）。
    tongyi_none = TongyiChat.model_construct(
        temperature=None,
        max_tokens=None,
        presence_penalty=None,
        frequency_penalty=None,
        enable_search=None,
    )
    assert tongyi_none._default_params == {"base": True}

    wenxin_none = WenxinChat.model_construct(
        max_output_tokens=None, disable_search=None
    )
    assert wenxin_none._default_params == {"base": True}


def test_moonshot_encoding_model_should_force_gpt35(monkeypatch):
    monkeypatch.setattr(
        "internal.core.language_model.providers.moonshot.chat.tiktoken.encoding_for_model",
        lambda model: f"encoding:{model}",
    )
    moonshot = object.__new__(MoonshotChat)

    model, encoding = MoonshotChat._get_encoding_model(moonshot)

    assert model == "gpt-3.5-turbo"
    assert encoding == "encoding:gpt-3.5-turbo"


def test_default_timeout_helper_should_fallback_when_env_is_empty(monkeypatch):
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT", "")

    from internal.core.language_model.providers._defaults import (
        apply_default_model_timeout,
    )

    resolved = apply_default_model_timeout({})

    assert resolved["timeout"] == 120.0
