"""公共工作流服务 - 处理工作流广场相关逻辑"""
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from injector import inject
from sqlalchemy import desc, or_

from internal.entity.workflow_entity import WorkflowStatus
from internal.entity.tag_entity import sort_tags_by_priority
from internal.lib.helper import datetime_to_timestamp
from internal.service.tag_assignment_service import TagAssignmentService
from internal.exception import NotFoundException, ForbiddenException, ValidateErrorException, FailException
from internal.model import (
    Workflow,
    Account,
)
from internal.schema.public_workflow_schema import GetPublicWorkflowsWithPageReq
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class PublicWorkflowService(BaseService):
    """公共工作流服务"""
    db: SQLAlchemy

    @staticmethod
    def _resolve_public_workflow_tags(workflow: Workflow) -> list[str]:
        """优先使用已保存标签；缺失时仅做轻量关键词兜底，避免列表接口触发慢路径。"""
        tags = list(getattr(workflow, "tags", []) or [])
        if tags:
            return sort_tags_by_priority(tags)
        tags = TagAssignmentService.match_tags_by_keywords(workflow.name, workflow.description)
        return tags if tags else ["other"]

    def share_workflow_to_square(self, workflow_id: UUID, tags: str, account: Account) -> Workflow:
        """将工作流共享到广场"""
        # 1.获取工作流并校验权限
        workflow = self.db.session.query(Workflow).filter(Workflow.id == workflow_id).one_or_none()
        if not workflow:
            raise NotFoundException("工作流不存在")

        if workflow.account_id != account.id:
            raise ForbiddenException("无权限操作该工作流")

        # 2.校验工作流是否已发布
        if workflow.status != WorkflowStatus.PUBLISHED.value:
            raise ValidateErrorException("只有已发布的工作流才能共享到广场")

        # 3.处理标签
        if tags:
            # 如果提供了标签，使用提供的标签
            tag_list = [t.strip() for t in tags.split(',') if t.strip()]
            tag_list = sort_tags_by_priority(tag_list)
            if not tag_list:
                tag_list = ["other"]
        else:
            # 如果没有提供标签，使用轻量关键词兜底，避免公开链路触发模型调用
            tag_list = TagAssignmentService.match_tags_by_keywords(workflow.name, workflow.description)
            if not tag_list:
                tag_list = ["other"]

        # 4.更新工作流为公开状态
        self.update(workflow, **{
            "is_public": True,
            "tags": tag_list,
            "published_at": datetime.now(UTC).replace(tzinfo=None),
        })

        logging.info(f"工作流已共享到广场: workflow_id={workflow_id}, tags={tag_list}")
        return workflow

    def unshare_workflow_from_square(self, workflow_id: UUID, account: Account) -> Workflow:
        """取消工作流从广场的共享"""
        # 1.获取工作流并校验权限
        workflow = self.db.session.query(Workflow).filter(Workflow.id == workflow_id).one_or_none()
        if not workflow:
            raise NotFoundException("工作流不存在")

        if workflow.account_id != account.id:
            raise ForbiddenException("无权限操作该工作流")

        # 2.更新工作流为非公开状态
        self.update(workflow, **{
            "is_public": False,
            "published_at": None,
        })

        logging.info(f"工作流已从广场取消共享: workflow_id={workflow_id}")
        return workflow

    def get_public_workflows_with_page(
            self,
            req: GetPublicWorkflowsWithPageReq,
            account: Account = None
    ) -> tuple[list[dict[str, Any]], Paginator]:
        """获取公共工作流广场列表"""
        # 1.构建分页器
        paginator = Paginator(db=self.db, req=req)

        # 2.构建筛选条件
        filters = [
            Workflow.is_public == True,
            Workflow.status == WorkflowStatus.PUBLISHED.value,
        ]
        requested_tags = [t.strip() for t in req.tags.data.split(',') if t.strip()] if req.tags.data else []

        if requested_tags:
            filters.append(or_(*[Workflow.tags.contains([tag]) for tag in requested_tags]))

        # 搜索词筛选
        if req.search_word.data:
            filters.append(
                or_(
                    Workflow.name.ilike(f"%{req.search_word.data}%"),
                    Workflow.description.ilike(f"%{req.search_word.data}%")
                )
            )

        query = (
            self.db.session.query(
                Workflow,
                Account.name.label("account_name"),
                Account.avatar.label("account_avatar"),
            )
            .join(Account, Account.id == Workflow.account_id)
            .filter(*filters)
            .order_by(desc(Workflow.published_at), desc(Workflow.created_at))
        )

        workflow_rows = paginator.paginate(query)

        workflow_ids = [workflow.id for workflow, _account_name, _account_avatar in workflow_rows]
        forked_workflow_ids: set[UUID] = set()
        if account and workflow_ids:
            # 查询用户是否fork过这些工作流（包括草稿状态）
            forked_workflow_ids = {
                row[0]
                for row in self.db.session.query(Workflow.original_workflow_id).filter(
                    Workflow.account_id == account.id,
                    Workflow.original_workflow_id.in_(workflow_ids),
                    Workflow.original_workflow_id.isnot(None),
                ).all()
            }

        # 6.构建返回数据
        result = []
        for workflow, account_name, account_avatar in workflow_rows:
            resolved_tags = self._resolve_public_workflow_tags(workflow)
            result.append({
                "id": str(workflow.id),
                "name": workflow.name,
                "icon": workflow.icon,
                "description": workflow.description,
                "tags": resolved_tags,
                "published_at": datetime_to_timestamp(workflow.published_at),
                "created_at": datetime_to_timestamp(workflow.created_at),
                "is_forked": workflow.id in forked_workflow_ids if account else False,
                "account_name": account_name or "Unknown",
                "account_avatar": account_avatar or "",
            })

        return result, paginator

    def fork_public_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """Fork公共工作流到个人空间"""
        # 1.获取公共工作流
        public_workflow = self.db.session.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.is_public == True,
            Workflow.status == WorkflowStatus.PUBLISHED.value
        ).one_or_none()

        if not public_workflow:
            raise NotFoundException("公共工作流不存在或未公开")

        # 2.复制工作流基础信息
        workflow_dict = {
            "account_id": account.id,
            "name": f"{public_workflow.name} (副本)",
            "tool_call_name": f"{public_workflow.tool_call_name}_copy_{account.id.hex[:8]}",
            "icon": public_workflow.icon,
            "description": public_workflow.description,
            "draft_graph": public_workflow.graph,  # 将发布的graph作为草稿
            "graph": {},
            "is_debug_passed": False,
            "status": WorkflowStatus.DRAFT.value,
            "tags": self._resolve_public_workflow_tags(public_workflow),
            "original_workflow_id": public_workflow.id,
        }

        # 3.创建新工作流
        with self.db.auto_commit():
            new_workflow = Workflow(**workflow_dict)
            self.db.session.add(new_workflow)
            self.db.session.flush()

        logging.info(f"工作流已Fork: original_workflow_id={workflow_id}, new_workflow_id={new_workflow.id}")
        return new_workflow

    def get_public_workflow_draft_graph(self, workflow_id: UUID) -> dict[str, Any]:
        """获取公共工作流的草稿图配置"""
        # 1.获取公共工作流
        workflow = self.db.session.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.is_public == True,
            Workflow.status == WorkflowStatus.PUBLISHED.value
        ).one_or_none()

        if not workflow:
            raise NotFoundException("公共工作流不存在或未公开")

        # 2.获取已发布的graph配置
        graph = workflow.graph or {"nodes": [], "edges": []}

        # 3.转换节点格式：将 node_type 转换为 type（Vue Flow 需要）
        if "nodes" in graph:
            for node in graph["nodes"]:
                if "node_type" in node:
                    node["type"] = node.pop("node_type")
                # 确保 data 字段存在
                if "data" not in node:
                    # 将除了 id, type, position 之外的所有字段放入 data
                    node_data = {k: v for k, v in node.items() if k not in ["id", "type", "position"]}
                    node["data"] = node_data
                    # 清理已移到 data 中的字段
                    for key in list(node_data.keys()):
                        if key in node and key not in ["id", "type", "position", "data"]:
                            del node[key]

        # 4.转换边格式：确保字段名正确
        if "edges" in graph:
            for edge in graph["edges"]:
                # 将 source_handle/target_handle 转换为 sourceHandle/targetHandle
                if "source_handle" in edge:
                    edge["sourceHandle"] = edge.pop("source_handle")
                if "target_handle" in edge:
                    edge["targetHandle"] = edge.pop("target_handle")

        return graph

    def get_public_workflow_detail(self, workflow_id: UUID, account: Account = None) -> dict[str, Any]:
        """获取公共工作流详情（包括基本信息和图配置）"""
        # 1.获取公共工作流
        workflow = self.db.session.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.is_public == True,
            Workflow.status == WorkflowStatus.PUBLISHED.value
        ).one_or_none()

        if not workflow:
            raise NotFoundException("公共工作流不存在或未公开")

        # 2.获取发布者信息
        account_obj = self.db.session.query(Account).filter(Account.id == workflow.account_id).one_or_none()

        # 3.构建工作流详情
        workflow_detail = {
            "id": str(workflow.id),
            "name": workflow.name,
            "icon": workflow.icon,
            "description": workflow.description,
            "tags": self._resolve_public_workflow_tags(workflow),
            "status": workflow.status,
            "is_public": workflow.is_public,
            "is_debug_passed": workflow.is_debug_passed,
            "account_name": account_obj.name if account_obj else "Unknown",
            "account_avatar": getattr(account_obj, "avatar", "") if account_obj else "",
            "published_at": datetime_to_timestamp(workflow.published_at),
            "created_at": datetime_to_timestamp(workflow.created_at),
            "updated_at": int(workflow.updated_at.timestamp()),
            "is_forked": False,  # 是否已fork
        }

        # 4.如果用户已登录，查询用户的 fork 状态
        if account:
            # 查询用户是否fork过该工作流（包括草稿状态）
            is_forked = self.db.session.query(Workflow).filter(
                Workflow.account_id == account.id,
                Workflow.original_workflow_id == workflow.id,
                Workflow.original_workflow_id.isnot(None),
            ).one_or_none() is not None

            workflow_detail["is_forked"] = is_forked

        return workflow_detail
