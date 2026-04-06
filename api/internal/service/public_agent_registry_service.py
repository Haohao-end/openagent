import logging
import re
from dataclasses import dataclass
from datetime import UTC
from typing import Any
from uuid import UUID

import httpx
from flask import Flask, current_app, has_app_context
from injector import inject
from langchain_core.documents import Document
from langchain_core.tools import BaseTool, tool
from openai import APIConnectionError
from pydantic import BaseModel, Field

from internal.entity.app_entity import AppStatus
from internal.model import App, Workflow
from pkg.sqlalchemy import SQLAlchemy

from .base_service import BaseService
from .faiss_service import FaissService

logger = logging.getLogger(__name__)


@inject
@dataclass
class PublicAgentRegistryService(BaseService):
    """公共Agent向量注册表服务。"""

    db: SQLAlchemy
    faiss_service: FaissService

    def build_agent_card_url(self, app_id: UUID | str) -> str:
        return f"/public/apps/{app_id}/a2a/agent-card"

    def build_agent_message_url(self, app_id: UUID | str) -> str:
        return f"/public/apps/{app_id}/a2a/messages"

    def sync_public_app(self, app_id: UUID) -> None:
        """根据当前应用状态同步索引。"""
        app = self.get(App, app_id)
        if not app or app.status != AppStatus.PUBLISHED.value or not app.is_public:
            self.remove_public_app(app_id)
            return

        self.upsert_public_app(app_id)

    def upsert_public_app(self, app_id: UUID) -> None:
        """将公开且已发布的应用写入向量索引。"""
        app = self.db.session.query(App).filter(
            App.id == app_id,
            App.status == AppStatus.PUBLISHED.value,
            App.is_public == True,
        ).one_or_none()
        if not app or not app.app_config:
            self.remove_public_app(app_id)
            return

        document = self.build_public_agent_document(app)
        self.faiss_service.upsert_documents([document])

    def remove_public_app(self, app_id: UUID) -> None:
        """将应用从向量索引移除。"""
        self.faiss_service.delete_by_app_ids([str(app_id)])

    def rebuild_public_agent_index(self) -> int:
        """重建公共Agent向量索引。"""
        apps = self.db.session.query(App).filter(
            App.status == AppStatus.PUBLISHED.value,
            App.is_public == True,
        ).all()

        self.faiss_service.recreate_public_agent_store()
        documents = [self.build_public_agent_document(app) for app in apps if app.app_config]
        if documents:
            self.faiss_service.upsert_documents(documents)

        return len(documents)

    def search_public_apps(
        self,
        query: str,
        limit: int = 3,
        metadata_filter: dict[str, Any] | None = None,
        exclude_app_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """检索公开应用并补齐展示字段。"""
        normalized_limit = max(1, min(int(limit or 3), 3))
        normalized_filter = metadata_filter or {"is_public": True}
        documents: list[Document] = []
        vector_search_available = True
        try:
            documents = self.faiss_service.search_public_agents(
                query=query,
                top_k=normalized_limit,
                metadata_filter=normalized_filter,
            )
        except (APIConnectionError, httpx.TransportError) as exc:
            vector_search_available = False
            self._log_vector_search_fallback("search", query, exc)

        if not documents and vector_search_available and self._has_public_apps():
            try:
                self.rebuild_public_agent_index()
                documents = self.faiss_service.search_public_agents(
                    query=query,
                    top_k=normalized_limit,
                    metadata_filter=normalized_filter,
                )
            except (APIConnectionError, httpx.TransportError) as exc:
                self._log_vector_search_fallback("rebuild", query, exc)
        if not documents:
            return self._search_public_apps_from_db(
                query=query,
                limit=normalized_limit,
                exclude_app_ids=exclude_app_ids,
            )

        excluded_ids = {str(app_id).strip() for app_id in (exclude_app_ids or []) if str(app_id).strip()}
        ordered_app_ids = []
        app_id_to_document: dict[str, Document] = {}
        for document in documents:
            app_id = str(document.metadata.get("app_id", "")).strip()
            if not app_id or app_id in excluded_ids:
                continue
            if app_id in app_id_to_document:
                continue
            ordered_app_ids.append(app_id)
            app_id_to_document[app_id] = document

        if not ordered_app_ids:
            return []

        valid_uuid_ids = []
        for app_id in ordered_app_ids:
            try:
                valid_uuid_ids.append(UUID(app_id))
            except Exception:
                continue

        if not valid_uuid_ids:
            return []

        app_rows = self.db.session.query(App).filter(
            App.id.in_(valid_uuid_ids),
            App.status == AppStatus.PUBLISHED.value,
            App.is_public == True,
        ).all()
        app_map = {str(app.id): app for app in app_rows}

        results = []
        for app_id in ordered_app_ids:
            app = app_map.get(app_id)
            document = app_id_to_document.get(app_id)
            if not app or not document:
                continue

            results.append(
                {
                    "app_id": app_id,
                    "name": app.name,
                    "description": app.description,
                    "tags": app.tags or [],
                    "published_at": document.metadata.get("published_at", 0),
                    "a2a_card_url": document.metadata.get("a2a_card_url", ""),
                    "a2a_message_url": document.metadata.get("a2a_message_url", ""),
                    "page_content": document.page_content,
                }
            )

        return results

    def _log_vector_search_fallback(self, stage: str, query: str, exc: Exception) -> None:
        logger.warning(
            "Public agent vector %s failed, falling back to database search. query=%s error=%s",
            stage,
            query,
            str(exc),
            exc_info=True,
        )

    def convert_public_agent_search_to_tool(self) -> BaseTool:
        """将公共Agent检索能力转换成 LangChain 工具。"""
        flask_app = current_app._get_current_object() if has_app_context() else None

        class PublicAgentSearchInput(BaseModel):
            """公共Agent检索工具输入结构"""

            query: str = Field(description="需要检索的Agent能力描述或用户问题")
            limit: int = Field(default=3, description="最多返回的Agent数量，建议不超过3")

        @tool("search_public_agents", args_schema=PublicAgentSearchInput)
        def search_public_agents(query: str, limit: int = 3) -> dict[str, Any]:
            """仅当你需要查看或比对已有公共Agent候选列表时，调用该工具。它会使用公共Agent注册表进行检索，并在本地索引为空时自动重建或回退数据库匹配；如果用户直接需要某个专业智能体给出答案，不要停在本工具，应继续调用 `route_public_agents` 获取最终结果。"""
            matches = self._search_public_apps_with_app_context(
                query=query,
                limit=min(max(int(limit or 3), 1), 3),
                metadata_filter={"is_public": True},
                flask_app=flask_app,
            )
            return {"matches": matches}

        return search_public_agents

    def _search_public_apps_with_app_context(
        self,
        query: str,
        limit: int,
        metadata_filter: dict[str, Any] | None,
        flask_app: Flask | None = None,
    ) -> list[dict[str, Any]]:
        """在需要时显式补充 Flask application context，再执行公开Agent检索。"""
        if flask_app is not None and not has_app_context():
            with flask_app.app_context():
                return self.search_public_apps(
                    query=query,
                    limit=limit,
                    metadata_filter=metadata_filter,
                )

        return self.search_public_apps(
            query=query,
            limit=limit,
            metadata_filter=metadata_filter,
        )

    def _has_public_apps(self) -> bool:
        """检测数据库中是否存在公开且已发布的应用。"""
        apps = self.db.session.query(App).filter(
            App.status == AppStatus.PUBLISHED.value,
            App.is_public == True,
        ).all()
        return len(apps) > 0

    def _search_public_apps_from_db(
        self,
        query: str,
        limit: int,
        exclude_app_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """当本地向量索引为空时，基于数据库字段做轻量级兜底匹配。"""
        excluded_ids = {str(app_id).strip() for app_id in (exclude_app_ids or []) if str(app_id).strip()}
        query_tokens = self._tokenize_search_text(query)
        if not query_tokens:
            return []

        app_rows = self.db.session.query(App).filter(
            App.status == AppStatus.PUBLISHED.value,
            App.is_public == True,
        ).all()

        scored_results = []
        for app in app_rows:
            app_id = str(app.id)
            if app_id in excluded_ids:
                continue

            searchable_text = self._build_searchable_text(app).lower()
            if not searchable_text:
                continue

            score = sum(1 for token in query_tokens if token in searchable_text)
            if query.strip() and str(app.name or "").strip() and str(app.name).strip().lower() in query.lower():
                score += 3
            if score <= 0:
                continue

            scored_results.append(
                (
                    score,
                    int(app.published_at.replace(tzinfo=UTC).timestamp()) if app.published_at else 0,
                    {
                        "app_id": app_id,
                        "name": app.name,
                        "description": app.description,
                        "tags": app.tags or [],
                        "published_at": int(app.published_at.replace(tzinfo=UTC).timestamp()) if app.published_at else 0,
                        "a2a_card_url": self.build_agent_card_url(app.id),
                        "a2a_message_url": self.build_agent_message_url(app.id),
                        "page_content": self.build_page_content(app, app.app_config),
                    },
                )
            )

        scored_results.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored_results[:limit]]

    def _build_searchable_text(self, app: App) -> str:
        """拼接可用于数据库兜底匹配的文本。"""
        app_config = app.app_config
        tags = " ".join(app.tags or [])
        opening_statement = app_config.opening_statement if app_config else ""
        tools_summary = self._build_tools_summary(app_config.tools if app_config else [])
        workflows_summary = self._build_workflows_summary(app_config.workflows if app_config else [])
        return " ".join(
            [
                str(app.name or ""),
                str(app.description or ""),
                tags,
                str(opening_statement or ""),
                tools_summary,
                workflows_summary,
            ]
        ).strip()

    @classmethod
    def _tokenize_search_text(cls, text: str) -> list[str]:
        """对中英文查询做轻量切分，兼容没有空格的中文短句。"""
        normalized = str(text or "").strip().lower()
        if not normalized:
            return []

        tokens = [
            token
            for token in re.split(r"[\s,，。！？、;；:/\\|()（）\[\]{}<>\"'`]+", normalized)
            if token
        ]
        compact = re.sub(r"\s+", "", normalized)
        if compact:
            tokens.append(compact)
            ngram_source = compact[:24]
            for window in (4, 3, 2):
                if len(ngram_source) >= window:
                    tokens.extend(
                        ngram_source[index:index + window]
                        for index in range(0, len(ngram_source) - window + 1)
                    )

        deduped_tokens = []
        seen = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            deduped_tokens.append(token)
        return deduped_tokens

    def build_public_agent_document(self, app: App) -> Document:
        """构建公共Agent索引文档。"""
        app_config = app.app_config
        page_content = self.build_page_content(app, app_config)
        metadata = self.build_metadata(app)
        return Document(page_content=page_content, metadata=metadata)

    def build_page_content(self, app: App, app_config: Any) -> str:
        """构建用于Embedding的公共Agent文本。"""
        tools_summary = self._build_tools_summary(app_config.tools if app_config else [])
        workflows_summary = self._build_workflows_summary(app_config.workflows if app_config else [])
        opening_statement = app_config.opening_statement if app_config else ""
        tags = ", ".join(app.tags or [])

        lines = [
            f"Agent名称: {app.name}",
            f"Agent描述: {app.description}",
            f"Agent标签: {tags}" if tags else "Agent标签: 无",
            f"开场白: {opening_statement}" if opening_statement else "开场白: 无",
            f"工具摘要: {tools_summary}" if tools_summary else "工具摘要: 无",
            f"工作流摘要: {workflows_summary}" if workflows_summary else "工作流摘要: 无",
        ]
        return "\n".join(lines)

    def build_metadata(self, app: App) -> dict[str, Any]:
        """构建公共Agent检索元数据。"""
        published_at = 0
        if app.published_at:
            published_at = int(app.published_at.replace(tzinfo=UTC).timestamp())

        return {
            "app_id": str(app.id),
            "is_public": bool(app.is_public),
            "published_at": published_at,
            "a2a_card_url": self.build_agent_card_url(app.id),
            "a2a_message_url": self.build_agent_message_url(app.id),
        }

    def _build_tools_summary(self, tools: list[dict[str, Any]] | None) -> str:
        if not tools:
            return ""
        summaries = []
        for tool in tools:
            provider_id = str(tool.get("provider_id", "")).strip()
            tool_id = str(tool.get("tool_id", "")).strip()
            if provider_id and tool_id:
                summaries.append(f"{provider_id}:{tool_id}")
        return ", ".join(summaries[:10])

    def _build_workflows_summary(self, workflow_ids: list[Any] | None) -> str:
        if not workflow_ids:
            return ""

        normalized_ids = []
        for workflow_id in workflow_ids:
            try:
                normalized_ids.append(UUID(str(workflow_id)))
            except Exception:
                continue

        if not normalized_ids:
            return ""

        workflow_rows = self.db.session.query(Workflow).filter(
            Workflow.id.in_(normalized_ids),
        ).all()
        workflow_map = {str(workflow.id): workflow for workflow in workflow_rows}
        summaries = []
        for workflow_id in workflow_ids:
            workflow = workflow_map.get(str(workflow_id))
            if not workflow:
                continue
            description = str(workflow.description or "").strip()
            if description:
                summaries.append(f"{workflow.name}:{description}")
            else:
                summaries.append(workflow.name)
        return ", ".join(summaries[:10])
