"""
标签服务

处理标签相关的业务逻辑。
"""

from uuid import UUID
from typing import Optional, List
from dataclasses import dataclass
from injector import inject
from sqlalchemy import and_

from internal.extension.database_extension import db
from internal.model import Tag, AppTag, WorkflowTag
from internal.entity.tag_entity import TagStatus, TagType
from internal.service.base_service import BaseService
from pkg.paginator import PageModel
from pkg.sqlalchemy import SQLAlchemy


@inject
@dataclass
class TagService(BaseService):
    """标签服务"""
    db: SQLAlchemy

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

    def update_tag(self, tag_id: UUID, **kwargs) -> Tag:
        """
        更新标签

        Args:
            tag_id: 标签 ID
            **kwargs: 更新的字段

        Returns:
            Tag: 更新后的标签
        """
        tag = self.get(Tag, tag_id)
        if not tag:
            return None
        return self.update(tag, **kwargs)

    def delete_tag(self, tag_id: UUID) -> Tag:
        """
        删除标签

        Args:
            tag_id: 标签 ID

        Returns:
            Tag: 删除的标签
        """
        tag = self.get(Tag, tag_id)
        if not tag:
            return None
        return self.delete(tag)

    def get_tag_by_id(self, tag_id: UUID) -> Optional[Tag]:
        """
        根据 ID 获取标签

        Args:
            tag_id: 标签 ID

        Returns:
            Tag: 标签对象
        """
        return self.get(Tag, tag_id)

    def get_tags_by_account(self, account_id: UUID, status: str = TagStatus.ACTIVE.value) -> List[Tag]:
        """
        获取账户的所有标签

        Args:
            account_id: 账户 ID
            status: 标签状态

        Returns:
            List[Tag]: 标签列表
        """
        return db.session.query(Tag).filter(
            and_(
                Tag.account_id == account_id,
                Tag.status == status,
            )
        ).all()

    def get_tags_with_page(
        self,
        account_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str = TagStatus.ACTIVE.value,
    ) -> PageModel:
        """
        分页获取账户的标签

        Args:
            account_id: 账户 ID
            page: 页码
            page_size: 每页数量
            status: 标签状态

        Returns:
            PageModel: 分页结果
        """
        query = db.session.query(Tag).filter(
            and_(
                Tag.account_id == account_id,
                Tag.status == status,
            )
        )

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        return PageModel(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

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
        existing = db.session.query(AppTag).filter(
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
        app_tag = db.session.query(AppTag).filter(
            and_(
                AppTag.app_id == app_id,
                AppTag.tag_id == tag_id,
            )
        ).one_or_none()

        if app_tag:
            self.delete(app_tag)
            return True
        return False

    def get_app_tags(self, app_id: UUID) -> List[Tag]:
        """
        获取应用的所有标签

        Args:
            app_id: 应用 ID

        Returns:
            List[Tag]: 标签列表
        """
        app_tags = db.session.query(AppTag).filter(AppTag.app_id == app_id).all()
        tag_ids = [at.tag_id for at in app_tags]
        if not tag_ids:
            return []
        return db.session.query(Tag).filter(Tag.id.in_(tag_ids)).all()

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
        existing = db.session.query(WorkflowTag).filter(
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
        workflow_tag = db.session.query(WorkflowTag).filter(
            and_(
                WorkflowTag.workflow_id == workflow_id,
                WorkflowTag.tag_id == tag_id,
            )
        ).one_or_none()

        if workflow_tag:
            self.delete(workflow_tag)
            return True
        return False

    def get_workflow_tags(self, workflow_id: UUID) -> List[Tag]:
        """
        获取工作流的所有标签

        Args:
            workflow_id: 工作流 ID

        Returns:
            List[Tag]: 标签列表
        """
        workflow_tags = db.session.query(WorkflowTag).filter(WorkflowTag.workflow_id == workflow_id).all()
        tag_ids = [wt.tag_id for wt in workflow_tags]
        if not tag_ids:
            return []
        return db.session.query(Tag).filter(Tag.id.in_(tag_ids)).all()
