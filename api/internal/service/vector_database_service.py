from injector import inject
from dataclasses import dataclass
from langchain_weaviate import WeaviateVectorStore
from weaviate.collections import Collection
from .embeddings_service import EmbeddingsService
from flask_weaviate import FlaskWeaviate

# 向量数据库的集合名字
COLLECTION_NAME = "Dataset"


@inject
@dataclass
class VectorDatabaseService:
    """向量数据库服务"""
    weaviate: FlaskWeaviate
    embeddings_service: EmbeddingsService

    @property
    def vector_store(self) -> WeaviateVectorStore:
        return WeaviateVectorStore(
            client=self.weaviate.client,
            index_name=COLLECTION_NAME,
            text_key="text",
            embedding=self.embeddings_service.cache_backed_embeddings
        )

    @property
    def collection(self) -> Collection:
        return self.weaviate.client.collections.get(COLLECTION_NAME)
