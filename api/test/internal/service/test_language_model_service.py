from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from internal.exception import NotFoundException
from internal.service.language_model_service import LanguageModelService


class _Provider:
    def __init__(self, provider_entity, models):
        self.provider_entity = provider_entity
        self.position = 1
        self._models = models

    def get_model_entities(self):
        return list(self._models.values())

    def get_model_entity(self, model_name: str):
        return self._models.get(model_name)

    @staticmethod
    def get_model_class(_model_type: str):
        return lambda **kwargs: SimpleNamespace(**kwargs)


def _build_service(manager):
    return LanguageModelService(db=SimpleNamespace(), language_model_manager=manager)


class TestLanguageModelService:
    def test_get_language_models_should_map_provider_and_models(self, monkeypatch):
        provider_entity = SimpleNamespace(
            name="openai",
            label="OpenAI",
            icon="openai.png",
            description="desc",
            background="#fff",
            supported_model_types=["chat"],
        )
        model_entity = SimpleNamespace(name="gpt-4o-mini")
        provider = _Provider(provider_entity=provider_entity, models={"gpt-4o-mini": model_entity})
        manager = SimpleNamespace(get_providers=lambda: [provider])
        service = _build_service(manager=manager)

        monkeypatch.setattr(
            "internal.service.language_model_service.convert_model_to_dict",
            lambda model_entities: [{"name": model_entities[0].name}],
        )

        result = service.get_language_models()

        assert result[0]["name"] == "openai"
        assert result[0]["label"] == "OpenAI"
        assert result[0]["models"][0]["name"] == "gpt-4o-mini"

    def test_get_language_model_should_raise_when_provider_not_found(self):
        service = _build_service(manager=SimpleNamespace(get_provider=lambda _name: None))

        with pytest.raises(NotFoundException):
            service.get_language_model("missing", "gpt-4o-mini")

    def test_get_language_model_should_raise_when_model_not_found(self):
        provider_entity = SimpleNamespace(name="openai")
        provider = _Provider(provider_entity=provider_entity, models={})
        service = _build_service(manager=SimpleNamespace(get_provider=lambda _name: provider))

        with pytest.raises(NotFoundException):
            service.get_language_model("openai", "missing-model")

    def test_get_language_model_should_return_serialized_model(self, monkeypatch):
        model_entity = SimpleNamespace(name="gpt-4o-mini")
        provider = _Provider(provider_entity=SimpleNamespace(name="openai"), models={"gpt-4o-mini": model_entity})
        service = _build_service(manager=SimpleNamespace(get_provider=lambda _name: provider))
        monkeypatch.setattr(
            "internal.service.language_model_service.convert_model_to_dict",
            lambda model: {"name": model.name, "model_type": "chat"},
        )

        result = service.get_language_model("openai", "gpt-4o-mini")

        assert result["name"] == "gpt-4o-mini"
        assert result["model_type"] == "chat"

    def test_get_language_model_icon_should_return_bytes_and_mimetype(self, tmp_path):
        root_path = Path(tmp_path)
        icon_path = root_path / "internal/core/language_model/providers/openai/_asset/openai.png"
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        icon_path.write_bytes(b"icon-bytes")

        # current_app.root_path 会向上回退两级，因此这里构造 api/app 目录让计算后回到 tmp_root。
        (root_path / "api/app").mkdir(parents=True, exist_ok=True)
        flask_app = Flask(__name__, root_path=str(root_path / "api/app"))

        provider_entity = SimpleNamespace(icon="openai.png")
        provider = SimpleNamespace(provider_entity=provider_entity)
        service = _build_service(manager=SimpleNamespace(get_provider=lambda _name: provider))

        with flask_app.app_context():
            content, mimetype = service.get_language_model_icon("openai")

        assert content == b"icon-bytes"
        assert mimetype == "image/png"

    def test_get_language_model_icon_should_raise_when_provider_missing(self):
        service = _build_service(manager=SimpleNamespace(get_provider=lambda _name: None))

        with pytest.raises(NotFoundException):
            service.get_language_model_icon("missing")

    def test_get_language_model_icon_should_raise_when_icon_missing(self, tmp_path):
        root_path = Path(tmp_path)
        (root_path / "api/app").mkdir(parents=True, exist_ok=True)
        flask_app = Flask(__name__, root_path=str(root_path / "api/app"))
        provider = SimpleNamespace(provider_entity=SimpleNamespace(icon="missing.png"))
        service = _build_service(manager=SimpleNamespace(get_provider=lambda _name: provider))

        with flask_app.app_context():
            with pytest.raises(NotFoundException):
                service.get_language_model_icon("openai")

    def test_load_language_model_should_fallback_to_default_model(self, monkeypatch):
        service = _build_service(manager=SimpleNamespace(get_provider=lambda _name: None))
        marker = SimpleNamespace(name="fallback-model")
        monkeypatch.setattr(service, "load_default_language_model", lambda: marker)

        result = service.load_language_model({"provider": "missing", "model": "x"})

        assert result is marker

    def test_load_language_model_should_build_model_instance_when_config_valid(self):
        model_entity = SimpleNamespace(
            model_type="chat",
            attributes={"model": "gpt-4o-mini", "temperature": 0.5},
            features=["tool_call"],
            metadata={"ctx": 8192},
        )
        provider = SimpleNamespace(
            get_model_entity=lambda _name: model_entity,
            get_model_class=lambda _type: (lambda **kwargs: SimpleNamespace(**kwargs)),
        )
        service = _build_service(manager=SimpleNamespace(get_provider=lambda _name: provider))

        llm = service.load_language_model(
            {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "parameters": {"max_tokens": 4096},
            }
        )

        assert llm.model == "gpt-4o-mini"
        assert llm.temperature == 0.5
        assert llm.max_tokens == 4096
        assert llm.features == ["tool_call"]
        assert llm.metadata == {"ctx": 8192}

    def test_load_default_language_model_should_use_expected_defaults(self):
        model_entity = SimpleNamespace(
            model_type="chat",
            attributes={"api_base": "https://api.example.com"},
            features=["tool_call"],
            metadata={"ctx": 8192},
        )
        provider = SimpleNamespace(
            get_model_entity=lambda _name: model_entity,
            get_model_class=lambda _type: (lambda **kwargs: SimpleNamespace(**kwargs)),
        )
        service = _build_service(manager=SimpleNamespace(get_provider=lambda _name: provider))

        llm = service.load_default_language_model()

        assert llm.temperature == 1
        assert llm.max_tokens == 8192
        assert llm.features == ["tool_call"]
        assert llm.metadata == {"ctx": 8192}
