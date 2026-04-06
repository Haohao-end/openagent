import os
from threading import RLock
from typing import Any

import faiss
from injector import inject
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from .embeddings_service import EmbeddingsService


@inject
class FaissService:
    """公共Agent本地向量数据库服务"""
    faiss: FAISS
    embeddings_service: EmbeddingsService

    def __init__(self, embeddings_service: EmbeddingsService):
        """构造函数，初始化公共Agent索引。"""
        self.embeddings_service = embeddings_service
        self._lock = RLock()

        internal_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.faiss_vector_store_path = os.path.join(internal_path, "core", "vector_store")
        os.makedirs(self.faiss_vector_store_path, exist_ok=True)
        self.faiss = self._load_or_create_vector_store()

    def _load_or_create_vector_store(self) -> FAISS:
        """加载本地索引；不存在时初始化一个空索引。"""
        if self._store_exists():
            return FAISS.load_local(
                folder_path=self.faiss_vector_store_path,
                embeddings=self.embeddings_service.cache_backed_embeddings,
                allow_dangerous_deserialization=True,
            )

        vector_store = self._create_empty_vector_store()
        vector_store.save_local(self.faiss_vector_store_path)
        return vector_store

    def _store_exists(self) -> bool:
        index_path = os.path.join(self.faiss_vector_store_path, "index.faiss")
        pickle_path = os.path.join(self.faiss_vector_store_path, "index.pkl")
        return os.path.exists(index_path) and os.path.exists(pickle_path)

    def _create_empty_vector_store(self) -> FAISS:
        """创建一个空的本地FAISS索引，避免首次启动依赖远程Embedding调用。"""
        index = faiss.IndexFlatL2(self.embeddings_service.embedding_dimension)
        return FAISS(
            embedding_function=self.embeddings_service.cache_backed_embeddings,
            index=index,
            docstore=InMemoryDocstore({}),
            index_to_docstore_id={},
        )

    def ensure_public_agent_store(self) -> None:
        """确保公共Agent索引已初始化并落盘。"""
        with self._lock:
            if not self._store_exists():
                self.faiss = self._create_empty_vector_store()
                self.save_local()

    def recreate_public_agent_store(self) -> None:
        """重建公共Agent索引并清空历史内容。"""
        with self._lock:
            self.faiss = self._create_empty_vector_store()
            self.save_local()

    def save_local(self) -> None:
        """将当前索引持久化到本地。"""
        with self._lock:
            self.faiss.save_local(self.faiss_vector_store_path)

    def upsert_documents(self, documents: list[Document]) -> None:
        """按 app_id upsert 文档。"""
        if not documents:
            return

        ids = [str(document.metadata.get("app_id", "")).strip() for document in documents]
        valid_pairs = [
            (document, document_id)
            for document, document_id in zip(documents, ids, strict=False)
            if document_id
        ]
        if not valid_pairs:
            return

        valid_ids = [document_id for _document, document_id in valid_pairs]
        valid_documents = [document for document, _document_id in valid_pairs]
        texts = [document.page_content for document in valid_documents]
        metadatas = [document.metadata for document in valid_documents]

        # Embed before mutating the in-memory index so transient network failures
        # do not leave the current process with a half-updated store.
        embeddings = self.embeddings_service.cache_backed_embeddings.embed_documents(texts)
        text_embeddings = list(zip(texts, embeddings, strict=False))

        with self._lock:
            existing_ids = self._get_existing_ids(valid_ids)
            if existing_ids:
                self.faiss.delete(ids=existing_ids)
            self.faiss.add_embeddings(
                text_embeddings=text_embeddings,
                metadatas=metadatas,
                ids=valid_ids,
            )
            self.faiss.save_local(self.faiss_vector_store_path)

    def delete_by_app_ids(self, app_ids: list[str]) -> None:
        """根据 app_id 删除指定文档。"""
        valid_ids = [str(app_id).strip() for app_id in app_ids if str(app_id).strip()]
        if not valid_ids:
            return

        with self._lock:
            existing_ids = self._get_existing_ids(valid_ids)
            if not existing_ids:
                return
            self.faiss.delete(ids=existing_ids)
            self.faiss.save_local(self.faiss_vector_store_path)

    def _get_existing_ids(self, ids: list[str]) -> list[str]:
        """仅返回当前索引中已存在的文档 id，避免 FAISS.delete 对缺失 id 抛错。"""
        existing_id_set = set(getattr(self.faiss, "index_to_docstore_id", {}).values())
        return [document_id for document_id in ids if document_id in existing_id_set]

    def search_public_agents(
        self,
        query: str,
        top_k: int = 3,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """检索公共Agent索引，并基于 metadata 做过滤。"""
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []

        self.ensure_public_agent_store()
        search_k = max(1, min(int(top_k or 3), 10))
        filter_dict = metadata_filter or {}

        with self._lock:
            if getattr(self.faiss.index, "ntotal", 0) <= 0:
                return []
            documents = self.faiss.similarity_search(
                normalized_query,
                k=search_k,
                filter=filter_dict or None,
                fetch_k=max(search_k * 3, 10),
            )

        if not filter_dict:
            return documents

        return [
            document
            for document in documents
            if all(document.metadata.get(key) == value for key, value in filter_dict.items())
        ]

    def convert_faiss_to_tool(self) -> BaseTool:
        """将公共Agent索引转换成 LangChain 工具。"""

        class PublicAgentSearchInput(BaseModel):
            """公共Agent检索工具输入结构"""

            query: str = Field(description="需要检索的Agent能力描述或用户问题")
            limit: int = Field(default=3, description="最多返回的Agent数量，建议不超过3")

        @tool("search_public_agents", args_schema=PublicAgentSearchInput)
        def search_public_agents(query: str, limit: int = 3) -> dict[str, Any]:
            """仅当你需要查看或比对已有公共Agent候选列表时，调用该工具。它只负责检索，不负责真正调用Agent；如果用户直接需要某个专业智能体给出答案，优先调用 `route_public_agents`，不要只把检索结果直接回复给用户。"""
            documents = self.search_public_agents(
                query=query,
                top_k=min(max(int(limit or 3), 1), 3),
                metadata_filter={"is_public": True},
            )
            return {
                "matches": [
                    {
                        "app_id": document.metadata.get("app_id", ""),
                        "published_at": document.metadata.get("published_at", 0),
                        "a2a_card_url": document.metadata.get("a2a_card_url", ""),
                        "a2a_message_url": document.metadata.get("a2a_message_url", ""),
                        "page_content": document.page_content,
                    }
                    for document in documents
                ]
            }

        return search_public_agents
