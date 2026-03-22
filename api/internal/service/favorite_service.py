"""收藏列表聚合服务"""
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from injector import inject

from internal.model import Account, AppFavorite, WorkflowFavorite
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
class FavoriteService:
    """聚合当前用户收藏的应用与工作流"""

    db: SQLAlchemy
    public_app_service: PublicAppService
    public_workflow_service: PublicWorkflowService

    def _build_app_items(self, account: Account) -> list[dict[str, Any]]:
        favorites = (
            self.db.session.query(AppFavorite)
            .filter(AppFavorite.account_id == account.id)
            .order_by(AppFavorite.created_at.desc())
            .all()
        )
        if not favorites:
            return []

        app_items = {
            item["id"]: item for item in self.public_app_service.get_my_favorites(account)
        }

        results: list[dict[str, Any]] = []
        for favorite in favorites:
            item = app_items.get(str(favorite.app_id))
            if not item:
                continue
            results.append(
                {
                    **item,
                    "resource_type": "app",
                    "creator_name": item.get("creator_name", "未知用户"),
                    "creator_avatar": item.get("creator_avatar", ""),
                    "action_at": _to_timestamp(favorite.created_at),
                }
            )

        return results

    def _build_workflow_items(self, account: Account) -> list[dict[str, Any]]:
        favorites = (
            self.db.session.query(WorkflowFavorite)
            .filter(WorkflowFavorite.account_id == account.id)
            .order_by(WorkflowFavorite.created_at.desc())
            .all()
        )
        if not favorites:
            return []

        workflow_items = {
            item["id"]: item for item in self.public_workflow_service.get_my_favorites(account)
        }

        results: list[dict[str, Any]] = []
        for favorite in favorites:
            item = workflow_items.get(str(favorite.workflow_id))
            if not item:
                continue
            results.append(
                {
                    **item,
                    "resource_type": "workflow",
                    "creator_name": item.get("account_name", "未知用户"),
                    "creator_avatar": item.get("account_avatar", ""),
                    "action_at": _to_timestamp(favorite.created_at),
                }
            )

        return results

    def get_favorites(
        self,
        account: Account,
        search_word: str = "",
        resource_type: str = "all",
    ) -> list[dict[str, Any]]:
        """获取当前用户收藏列表，支持应用/工作流混排"""

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
