"""点赞列表聚合服务"""
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from injector import inject

from internal.model import Account, AppLike, WorkflowLike
from pkg.sqlalchemy import SQLAlchemy
from .public_app_service import PublicAppService
from .public_workflow_service import PublicWorkflowService


def _to_timestamp(value: datetime | None) -> int:
    if not value:
        return 0
    if value.tzinfo is None:
        return int(value.replace(tzinfo=UTC).timestamp())
    return int(value.timestamp())


def _match_search(item: dict[str, Any], search_word: str) -> bool:
    if not search_word:
        return True

    keyword = search_word.strip().lower()
    if not keyword:
        return True

    candidates = [
        str(item.get("name", "")),
        str(item.get("description", "")),
        str(item.get("creator_name", "")),
    ]
    return any(keyword in candidate.lower() for candidate in candidates)


@inject
@dataclass
class LikeService:
    """聚合当前用户点赞的应用与工作流"""

    db: SQLAlchemy
    public_app_service: PublicAppService
    public_workflow_service: PublicWorkflowService

    def _build_app_items(self, account: Account) -> list[dict[str, Any]]:
        likes = (
            self.db.session.query(AppLike)
            .filter(AppLike.account_id == account.id)
            .order_by(AppLike.created_at.desc())
            .all()
        )
        if not likes:
            return []

        app_items = {
            item["id"]: item for item in self.public_app_service.get_my_likes(account)
        }

        results: list[dict[str, Any]] = []
        for like in likes:
            item = app_items.get(str(like.app_id))
            if not item:
                continue
            results.append(
                {
                    **item,
                    "resource_type": "app",
                    "creator_name": item.get("creator_name", "未知用户"),
                    "creator_avatar": item.get("creator_avatar", ""),
                    "action_at": _to_timestamp(like.created_at),
                }
            )

        return results

    def _build_workflow_items(self, account: Account) -> list[dict[str, Any]]:
        likes = (
            self.db.session.query(WorkflowLike)
            .filter(WorkflowLike.account_id == account.id)
            .order_by(WorkflowLike.created_at.desc())
            .all()
        )
        if not likes:
            return []

        workflow_items = {
            item["id"]: item for item in self.public_workflow_service.get_my_likes(account)
        }

        results: list[dict[str, Any]] = []
        for like in likes:
            item = workflow_items.get(str(like.workflow_id))
            if not item:
                continue
            results.append(
                {
                    **item,
                    "resource_type": "workflow",
                    "creator_name": item.get("account_name", "未知用户"),
                    "creator_avatar": item.get("account_avatar", ""),
                    "action_at": _to_timestamp(like.created_at),
                }
            )

        return results

    def get_likes(
        self,
        account: Account,
        search_word: str = "",
        resource_type: str = "all",
    ) -> list[dict[str, Any]]:
        """获取当前用户点赞列表，支持应用/工作流混排"""

        items: list[dict[str, Any]] = []

        if resource_type in {"all", "app"}:
            items.extend(self._build_app_items(account))

        if resource_type in {"all", "workflow"}:
            items.extend(self._build_workflow_items(account))

        filtered_items = [item for item in items if _match_search(item, search_word)]
        filtered_items.sort(
            key=lambda item: (item.get("action_at", 0), item.get("created_at", 0)),
            reverse=True,
        )
        return filtered_items
