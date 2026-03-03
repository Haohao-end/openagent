"""公共工作流服务 - 处理工作流广场相关逻辑"""
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from injector import inject
from sqlalchemy import desc, or_, func

from internal.entity.app_category_entity import AppCategory
from internal.entity.workflow_entity import WorkflowStatus
from internal.exception import NotFoundException, ForbiddenException, ValidateErrorException, FailException
from internal.model import (
    Workflow,
    WorkflowLike,
    WorkflowFavorite,
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

    def share_workflow_to_square(self, workflow_id: UUID, category: str, account: Account) -> Workflow:
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

        # 3.校验分类是否有效
        valid_categories = [c.value for c in AppCategory]
        if category not in valid_categories:
            raise ValidateErrorException(f"无效的分类: {category}")

        # 4.更新工作流为公开状态
        self.update(workflow, **{
            "is_public": True,
            "category": category,
            "published_at": datetime.now(UTC).replace(tzinfo=None),
        })

        logging.info(f"工作流已共享到广场: workflow_id={workflow_id}, category={category}")
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

        # 分类筛选
        if req.category.data and req.category.data != "all":
            filters.append(Workflow.category == req.category.data)

        # 搜索词筛选
        if req.search_word.data:
            filters.append(
                or_(
                    Workflow.name.ilike(f"%{req.search_word.data}%"),
                    Workflow.description.ilike(f"%{req.search_word.data}%")
                )
            )

        # 3.收藏数量子查询（避免逐条 count）
        favorite_count_subquery = (
            self.db.session.query(
                WorkflowFavorite.workflow_id.label("workflow_id"),
                func.count(WorkflowFavorite.id).label("favorite_count"),
            )
            .group_by(WorkflowFavorite.workflow_id)
            .subquery()
        )

        # 4.构建主查询（同时拿到发布者名称 + 收藏数）
        query = (
            self.db.session.query(
                Workflow,
                Account.name.label("account_name"),
                func.coalesce(favorite_count_subquery.c.favorite_count, 0).label("favorite_count"),
            )
            .join(Account, Account.id == Workflow.account_id)
            .outerjoin(favorite_count_subquery, favorite_count_subquery.c.workflow_id == Workflow.id)
            .filter(*filters)
        )

        # 5.构建排序规则
        order_by_map = {
            "latest": desc(Workflow.published_at),
            "popular": desc(Workflow.view_count),
            "most_liked": desc(Workflow.like_count),
            "most_favorited": desc(func.coalesce(favorite_count_subquery.c.favorite_count, 0)),
            "most_forked": desc(Workflow.fork_count),
        }
        order_by = order_by_map.get(req.sort_by.data, desc(Workflow.like_count))
        query = query.order_by(order_by, desc(Workflow.created_at))
        workflow_rows = paginator.paginate(query)

        workflow_ids = [workflow.id for workflow, _account_name, _favorite_count in workflow_rows]
        liked_workflow_ids: set[UUID] = set()
        favorited_workflow_ids: set[UUID] = set()
        if account and workflow_ids:
            liked_workflow_ids = {
                row[0]
                for row in self.db.session.query(WorkflowLike.workflow_id).filter(
                    WorkflowLike.account_id == account.id,
                    WorkflowLike.workflow_id.in_(workflow_ids),
                ).all()
            }
            favorited_workflow_ids = {
                row[0]
                for row in self.db.session.query(WorkflowFavorite.workflow_id).filter(
                    WorkflowFavorite.account_id == account.id,
                    WorkflowFavorite.workflow_id.in_(workflow_ids),
                ).all()
            }

        # 6.构建返回数据
        result = []
        for workflow, account_name, favorite_count in workflow_rows:
            result.append({
                "id": str(workflow.id),
                "name": workflow.name,
                "icon": workflow.icon,
                "description": workflow.description,
                "category": workflow.category,
                "view_count": workflow.view_count,
                "like_count": workflow.like_count,
                "fork_count": workflow.fork_count,
                "favorite_count": favorite_count,
                "published_at": int(workflow.published_at.timestamp()) if workflow.published_at else 0,
                "created_at": int(workflow.created_at.timestamp()),
                "is_liked": workflow.id in liked_workflow_ids if account else False,
                "is_favorited": workflow.id in favorited_workflow_ids if account else False,
                "account_name": account_name or "Unknown",
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

        # 2.增加浏览次数
        self.update(public_workflow, view_count=public_workflow.view_count + 1)

        # 3.复制工作流基础信息
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
            "category": public_workflow.category,
            "original_workflow_id": public_workflow.id,
        }

        # 4.创建新工作流
        with self.db.auto_commit():
            new_workflow = Workflow(**workflow_dict)
            self.db.session.add(new_workflow)
            self.db.session.flush()

        # 5.增加原工作流的Fork计数
        self.update(public_workflow, fork_count=public_workflow.fork_count + 1)

        logging.info(f"工作流已Fork: original_workflow_id={workflow_id}, new_workflow_id={new_workflow.id}")
        return new_workflow

    def like_workflow(self, workflow_id: UUID, account: Account) -> dict[str, Any]:
        """点赞工作流"""
        # 1.获取工作流
        workflow = self.db.session.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.is_public == True
        ).one_or_none()

        if not workflow:
            raise NotFoundException("工作流不存在或未公开")

        # 2.检查是否已点赞
        existing_like = self.db.session.query(WorkflowLike).filter(
            WorkflowLike.workflow_id == workflow_id,
            WorkflowLike.account_id == account.id
        ).one_or_none()

        if existing_like:
            # 已点赞,则取消点赞
            self.db.session.delete(existing_like)
            self.update(workflow, like_count=max(0, workflow.like_count - 1))
            self.db.session.commit()
            return {"is_liked": False, "like_count": workflow.like_count}
        else:
            # 未点赞,则添加点赞
            new_like = WorkflowLike(workflow_id=workflow_id, account_id=account.id)
            self.db.session.add(new_like)
            self.update(workflow, like_count=workflow.like_count + 1)
            self.db.session.commit()
            return {"is_liked": True, "like_count": workflow.like_count}

    def favorite_workflow(self, workflow_id: UUID, account: Account) -> dict[str, Any]:
        """收藏工作流"""
        # 1.获取工作流
        workflow = self.db.session.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.is_public == True
        ).one_or_none()

        if not workflow:
            raise NotFoundException("工作流不存在或未公开")

        # 2.检查是否已收藏
        existing_favorite = self.db.session.query(WorkflowFavorite).filter(
            WorkflowFavorite.workflow_id == workflow_id,
            WorkflowFavorite.account_id == account.id
        ).one_or_none()

        if existing_favorite:
            # 已收藏,则取消收藏
            self.db.session.delete(existing_favorite)
            self.db.session.commit()
            is_favorited = False
        else:
            # 未收藏,则添加收藏
            new_favorite = WorkflowFavorite(workflow_id=workflow_id, account_id=account.id)
            self.db.session.add(new_favorite)
            self.db.session.commit()
            is_favorited = True

        # 3.查询最新的收藏数
        favorite_count = self.db.session.query(WorkflowFavorite).filter(
            WorkflowFavorite.workflow_id == workflow_id
        ).count()

        return {"is_favorited": is_favorited, "favorite_count": favorite_count}

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

        # 2.增加浏览次数
        self.update(workflow, view_count=workflow.view_count + 1)

        # 3.获取发布者信息
        account_obj = self.db.session.query(Account).filter(Account.id == workflow.account_id).one_or_none()

        # 4.计算收藏数
        favorite_count = self.db.session.query(func.count(WorkflowFavorite.id)).filter(
            WorkflowFavorite.workflow_id == workflow.id
        ).scalar() or 0

        # 5.构建工作流详情
        workflow_detail = {
            "id": str(workflow.id),
            "name": workflow.name,
            "icon": workflow.icon,
            "description": workflow.description,
            "category": workflow.category,
            "status": workflow.status,
            "is_public": workflow.is_public,
            "is_debug_passed": workflow.is_debug_passed,
            "view_count": workflow.view_count,
            "like_count": workflow.like_count,
            "fork_count": workflow.fork_count,
            "favorite_count": favorite_count,
            "account_name": account_obj.name if account_obj else "Unknown",
            "published_at": int(workflow.published_at.timestamp()) if workflow.published_at else 0,
            "created_at": int(workflow.created_at.timestamp()),
            "updated_at": int(workflow.updated_at.timestamp()),
            "is_liked": False,
            "is_favorited": False,
        }

        # 6.如果用户已登录，查询用户的点赞和收藏状态
        if account:
            is_liked = self.db.session.query(WorkflowLike).filter(
                WorkflowLike.workflow_id == workflow.id,
                WorkflowLike.account_id == account.id
            ).one_or_none() is not None

            is_favorited = self.db.session.query(WorkflowFavorite).filter(
                WorkflowFavorite.workflow_id == workflow.id,
                WorkflowFavorite.account_id == account.id
            ).one_or_none() is not None

            workflow_detail["is_liked"] = is_liked
            workflow_detail["is_favorited"] = is_favorited

        return workflow_detail
