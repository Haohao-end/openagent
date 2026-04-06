"""
标签服务

处理标签相关的业务逻辑。
"""

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from injector import inject
from sqlalchemy import and_, desc, func

from internal.entity.tag_entity import TagStatus, TagType
from internal.model import AppTag, Tag, WorkflowTag
from internal.service.base_service import BaseService
from pkg.paginator import Paginator, PaginatorReq
from pkg.sqlalchemy import SQLAlchemy


@inject
@dataclass
class TagService(BaseService):
    """标签服务"""
    db: SQLAlchemy

    TAG_DIMENSIONS = [
        {"value": TagType.CUSTOM.value, "label": "自定义标签"},
        {"value": TagType.SYSTEM.value, "label": "系统标签"},
        {"value": TagType.CATEGORY.value, "label": "分类标签"},
    ]

    def _get_owned_tag(self, tag_id: UUID, account_id: UUID) -> Optional[Tag]:
        """只返回归属于当前账号的标签。"""
        return (
            self.db.session.query(Tag)
            .filter(
                and_(
                    Tag.id == tag_id,
                    Tag.account_id == account_id,
                )
            )
            .one_or_none()
        )

    def create_tag(self, account_id: UUID, name: str, description: str = "", tag_type: str = TagType.CUSTOM.value) -> Tag:
        """
        创建标签

        Args:
            account_id: 账户 ID
            name: 标签名称
            description: 标签描述
            tag_type: 标签类型

        Returns:
            Tag: 创建的标签
        """
        return self.create(
            Tag,
            account_id=account_id,
            name=name,
            description=description,
            tag_type=tag_type,
            status=TagStatus.ACTIVE.value,
        )

    def update_tag(self, tag_id: UUID, account_id: UUID, **kwargs) -> Optional[Tag]:
        """
        更新标签

        Args:
            tag_id: 标签 ID
            **kwargs: 更新的字段

        Returns:
            Tag: 更新后的标签
        """
        tag = self._get_owned_tag(tag_id, account_id)
        if not tag:
            return None
        return self.update(tag, **kwargs)

    def delete_tag(self, tag_id: UUID, account_id: UUID) -> Optional[Tag]:
        """
        删除标签

        Args:
            tag_id: 标签 ID

        Returns:
            Tag: 删除的标签
        """
        tag = self._get_owned_tag(tag_id, account_id)
        if not tag:
            return None
        return self.delete(tag)

    def get_tag_by_id(self, tag_id: UUID, account_id: UUID) -> Optional[Tag]:
        """
        根据 ID 获取标签

        Args:
            tag_id: 标签 ID

        Returns:
            Tag: 标签对象
        """
        return self._get_owned_tag(tag_id, account_id)

    def get_tags_by_account(self, account_id: UUID, status: str = TagStatus.ACTIVE.value) -> list[Tag]:
        """
        获取账户的所有标签

        Args:
            account_id: 账户 ID
            status: 标签状态

        Returns:
            List[Tag]: 标签列表
        """
        return self.db.session.query(Tag).filter(
            and_(
                Tag.account_id == account_id,
                Tag.status == status,
            )
        ).all()

    def get_tags_with_page(
        self,
        req: PaginatorReq,
        account_id: UUID,
        status: str = TagStatus.ACTIVE.value,
    ) -> tuple[list[Tag], Paginator]:
        """
        分页获取账户的标签

        Args:
            req: 分页请求
            account_id: 账户 ID
            status: 标签状态

        Returns:
            tuple[list[Tag], Paginator]: 分页结果
        """
        paginator = Paginator(db=self.db, req=req)
        tags = paginator.paginate(
            self.db.session.query(Tag).filter(
                and_(
                    Tag.account_id == account_id,
                    Tag.status == status,
                )
            ).order_by(desc(Tag.created_at))
        )

        return tags, paginator

    def get_tag_dimensions(self) -> list[dict[str, str]]:
        """获取标签维度定义。"""
        return self.TAG_DIMENSIONS

    def get_hot_tags(
        self,
        status: str = TagStatus.ACTIVE.value,
        limit_per_dimension: int = 10,
    ) -> dict[str, list[dict[str, Any]]]:
        """按标签类型分组，返回热门标签。"""
        app_tag_counts = dict(
            self.db.session.query(
                AppTag.tag_id,
                func.count(AppTag.id),
            ).group_by(AppTag.tag_id).all()
        )
        workflow_tag_counts = dict(
            self.db.session.query(
                WorkflowTag.tag_id,
                func.count(WorkflowTag.id),
            ).group_by(WorkflowTag.tag_id).all()
        )
        tags = (
            self.db.session.query(Tag)
            .filter(Tag.status == status)
            .order_by(desc(Tag.created_at))
            .all()
        )

        grouped_tags: dict[str, list[dict[str, Any]]] = {
            dimension["value"]: [] for dimension in self.TAG_DIMENSIONS
        }
        for tag in tags:
            use_count = int(app_tag_counts.get(tag.id, 0)) + int(workflow_tag_counts.get(tag.id, 0))
            grouped_tags.setdefault(tag.tag_type, [])
            grouped_tags[tag.tag_type].append(
                {
                    "id": str(tag.id),
                    "name": tag.name,
                    "dimension": tag.tag_type,
                    "use_count": use_count,
                }
            )

        normalized_hot_tags = {}
        for dimension, records in grouped_tags.items():
            sorted_records = sorted(
                records,
                key=lambda item: (-item["use_count"], item["name"]),
            )
            normalized_hot_tags[dimension] = sorted_records[:limit_per_dimension]

        return normalized_hot_tags

    def add_app_tag(self, account_id: UUID, app_id: UUID, tag_id: UUID) -> AppTag:
        """
        为应用添加标签

        Args:
            account_id: 账户 ID
            app_id: 应用 ID
            tag_id: 标签 ID

        Returns:
            AppTag: 应用标签关联
        """
        # 检查是否已存在
        existing = self.db.session.query(AppTag).filter(
            and_(
                AppTag.app_id == app_id,
                AppTag.tag_id == tag_id,
            )
        ).one_or_none()

        if existing:
            return existing

        return self.create(
            AppTag,
            account_id=account_id,
            app_id=app_id,
            tag_id=tag_id,
        )

    def remove_app_tag(self, app_id: UUID, tag_id: UUID) -> bool:
        """
        移除应用标签

        Args:
            app_id: 应用 ID
            tag_id: 标签 ID

        Returns:
            bool: 是否成功
        """
        app_tag = self.db.session.query(AppTag).filter(
            and_(
                AppTag.app_id == app_id,
                AppTag.tag_id == tag_id,
            )
        ).one_or_none()

        if app_tag:
            self.delete(app_tag)
            return True
        return False

    def get_app_tags(self, app_id: UUID) -> list[Tag]:
        """
        获取应用的所有标签

        Args:
            app_id: 应用 ID

        Returns:
            List[Tag]: 标签列表
        """
        app_tags = self.db.session.query(AppTag).filter(AppTag.app_id == app_id).all()
        tag_ids = [at.tag_id for at in app_tags]
        if not tag_ids:
            return []
        return self.db.session.query(Tag).filter(Tag.id.in_(tag_ids)).all()

    def add_workflow_tag(self, account_id: UUID, workflow_id: UUID, tag_id: UUID) -> WorkflowTag:
        """
        为工作流添加标签

        Args:
            account_id: 账户 ID
            workflow_id: 工作流 ID
            tag_id: 标签 ID

        Returns:
            WorkflowTag: 工作流标签关联
        """
        # 检查是否已存在
        existing = self.db.session.query(WorkflowTag).filter(
            and_(
                WorkflowTag.workflow_id == workflow_id,
                WorkflowTag.tag_id == tag_id,
            )
        ).one_or_none()

        if existing:
            return existing

        return self.create(
            WorkflowTag,
            account_id=account_id,
            workflow_id=workflow_id,
            tag_id=tag_id,
        )

    def remove_workflow_tag(self, workflow_id: UUID, tag_id: UUID) -> bool:
        """
        移除工作流标签

        Args:
            workflow_id: 工作流 ID
            tag_id: 标签 ID

        Returns:
            bool: 是否成功
        """
        workflow_tag = self.db.session.query(WorkflowTag).filter(
            and_(
                WorkflowTag.workflow_id == workflow_id,
                WorkflowTag.tag_id == tag_id,
            )
        ).one_or_none()

        if workflow_tag:
            self.delete(workflow_tag)
            return True
        return False

    def get_workflow_tags(self, workflow_id: UUID) -> list[Tag]:
        """
        获取工作流的所有标签

        Args:
            workflow_id: 工作流 ID

        Returns:
            List[Tag]: 标签列表
        """
        workflow_tags = self.db.session.query(WorkflowTag).filter(WorkflowTag.workflow_id == workflow_id).all()
        tag_ids = [wt.tag_id for wt in workflow_tags]
        if not tag_ids:
            return []
        return self.db.session.query(Tag).filter(Tag.id.in_(tag_ids)).all()
