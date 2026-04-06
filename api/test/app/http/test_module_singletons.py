from injector import Injector

from app.http import module as http_module
from internal.service.embeddings_service import EmbeddingsService
from internal.service.faiss_service import FaissService
from internal.service.public_agent_registry_service import PublicAgentRegistryService


def _build_injector_with_stubbed_infra(monkeypatch):
    fake_vector_store = object()
    fake_store = object()
    fake_embeddings_client = object()
    fake_cache_backed_embeddings = object()

    monkeypatch.setattr(
        "internal.service.embeddings_service.RedisStore",
        lambda client: fake_store,
    )
    monkeypatch.setattr(
        "internal.service.embeddings_service.OpenAIEmbeddings",
        lambda model: fake_embeddings_client,
    )
    monkeypatch.setattr(
        "internal.service.embeddings_service.CacheBackedEmbeddings.from_bytes_store",
        staticmethod(
            lambda _embeddings, _store, namespace, key_encoder: fake_cache_backed_embeddings
        ),
    )
    monkeypatch.setattr(
        "internal.service.faiss_service.os.makedirs",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "internal.service.faiss_service.FaissService._load_or_create_vector_store",
        lambda self: fake_vector_store,
    )

    injector = Injector([http_module.ExtensionModule])
    return injector, fake_vector_store, fake_embeddings_client, fake_cache_backed_embeddings


def test_extension_module_should_bind_embeddings_and_faiss_as_singletons(monkeypatch):
    injector, fake_vector_store, fake_embeddings_client, fake_cache_backed_embeddings = (
        _build_injector_with_stubbed_infra(monkeypatch)
    )

    embeddings_service = injector.get(EmbeddingsService)
    same_embeddings_service = injector.get(EmbeddingsService)
    faiss_service = injector.get(FaissService)
    same_faiss_service = injector.get(FaissService)

    assert embeddings_service is same_embeddings_service
    assert faiss_service is same_faiss_service
    assert faiss_service.embeddings_service is embeddings_service
    assert embeddings_service.embeddings is fake_embeddings_client
    assert embeddings_service.cache_backed_embeddings is fake_cache_backed_embeddings
    assert faiss_service.faiss is fake_vector_store


def test_public_agent_registry_service_should_reuse_singleton_faiss_service(monkeypatch):
    injector, _fake_vector_store, _fake_embeddings_client, _fake_cache_backed_embeddings = (
        _build_injector_with_stubbed_infra(monkeypatch)
    )

    faiss_service = injector.get(FaissService)
    embeddings_service = injector.get(EmbeddingsService)
    registry_service = injector.get(PublicAgentRegistryService)

    assert registry_service.faiss_service is faiss_service
    assert registry_service.faiss_service.embeddings_service is embeddings_service
