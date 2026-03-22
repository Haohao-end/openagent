"""公共应用服务 - 处理应用广场相关逻辑"""
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from injector import inject
from sqlalchemy import func, or_

from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.entity.app_category_entity import AppCategory
from internal.entity.app_entity import AppStatus
from internal.entity.workflow_entity import WorkflowStatus
from internal.entity.tag_entity import sort_tags_by_priority
from internal.service.tag_assignment_service import TagAssignmentService
from internal.exception import NotFoundException, ForbiddenException, ValidateErrorException, FailException
from internal.model import (
    App,
    AppConfigVersion,
    AppDatasetJoin,
    AppLike,
    AppFavorite,
    Account,
    ApiToolProvider,
    ApiTool,
    Workflow,
)
from internal.schema.public_app_schema import GetPublicAppsWithPageReq
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class PublicAppService(BaseService):
    """公共应用服务"""
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager

    def _enrich_tools(self, tools: list[dict]) -> list[dict]:
        """填充工具的完整信息（provider 和 tool 的 label、icon 等）"""
        enriched_tools = []

        for tool in tools:
            if tool["type"] == "builtin_tool":
                # 获取内置工具提供者
                provider = self.builtin_provider_manager.get_provider(tool.get("provider_id", ""))
                if not provider:
                    continue

                # 获取工具实体
                tool_entity = provider.get_tool_entity(tool.get("tool_id", ""))
                if not tool_entity:
                    continue

                # 组装完整信息
                provider_entity = provider.provider_entity
                enriched_tools.append({
                    "type": "builtin_tool",
                    "provider": {
                        "id": provider_entity.name,
                        "name": provider_entity.name,
                        "label": provider_entity.label,
                        "icon": f"/builtin-tools/{provider_entity.name}/icon",
                        "description": provider_entity.description,
                    },
                    "tool": {
                        "id": tool_entity.name,
                        "name": tool_entity.name,
                        "label": tool_entity.label,
                        "description": tool_entity.description,
                        "params": tool.get("params", {}),
                    }
                })
            elif tool["type"] == "api_tool":
                # 查询 API 工具
                api_tool = self.db.session.query(ApiTool).filter(
                    ApiTool.id == tool.get("tool_id")
                ).one_or_none()

                if not api_tool:
                    continue

                # 查询 API 提供者
                api_provider = self.db.session.query(ApiToolProvider).filter(
                    ApiToolProvider.id == tool.get("provider_id")
                ).one_or_none()

                if not api_provider:
                    continue

                # 组装完整信息
                enriched_tools.append({
                    "type": "api_tool",
                    "provider": {
                        "id": str(api_provider.id),
                        "name": api_provider.name,
                        "label": api_provider.name,
                        "icon": api_provider.icon,
                        "description": api_provider.description,
                    },
                    "tool": {
                        "id": str(api_tool.id),
                        "name": api_tool.name,
                        "label": api_tool.name,
                        "description": api_tool.description,
                        "params": tool.get("params", {}),
                    }
                })

        return enriched_tools

    def _enrich_workflows(self, workflows: list[Any] | None) -> list[dict]:
        """填充工作流完整信息（name/icon/description），保持原始顺序。"""
        if not workflows:
            return []

        workflow_entries: list[dict[str, str]] = []
        workflow_ids: list[str] = []

        for workflow in workflows:
            if workflow is None:
                continue

            workflow_id = ""
            workflow_name = ""
            workflow_icon = ""
            workflow_description = ""

            if isinstance(workflow, dict):
                workflow_id = str(workflow.get("id", "")).strip()
                workflow_name = str(workflow.get("name", "")).strip()
                workflow_icon = str(workflow.get("icon", "")).strip()
                workflow_description = str(workflow.get("description", "")).strip()
            else:
                workflow_id = str(workflow).strip()

            if not workflow_id:
                continue

            workflow_entries.append(
                {
                    "id": workflow_id,
                    "name": workflow_name,
                    "icon": workflow_icon,
                    "description": workflow_description,
                }
            )
            workflow_ids.append(workflow_id)

        if not workflow_entries:
            return []

        # 仅补齐已发布工作流信息，避免暴露非发布工作流详情。
        workflow_records = (
            self.db.session.query(Workflow)
            .filter(
                Workflow.id.in_(workflow_ids),
                Workflow.status == WorkflowStatus.PUBLISHED.value,
            )
            .all()
        )
        workflow_record_map = {str(workflow.id): workflow for workflow in workflow_records}

        enriched_workflows: list[dict] = []
        for workflow_entry in workflow_entries:
            workflow = workflow_record_map.get(workflow_entry["id"])
            if workflow:
                enriched_workflows.append(
                    {
                        "id": str(workflow.id),
                        "name": workflow.name,
                        "icon": workflow.icon,
                        "description": workflow.description,
                    }
                )
                continue

            enriched_workflows.append(workflow_entry)

        return enriched_workflows

    def share_app_to_square(self, app_id: UUID, tags: str, account: Account) -> App:
        """将应用共享到广场"""
        # 1.获取应用并校验权限
        app = self.db.session.query(App).filter(App.id == app_id).one_or_none()
        if not app:
            raise NotFoundException("应用不存在")

        if app.account_id != account.id:
            raise ForbiddenException("无权限操作该应用")

        # 2.校验应用是否已发布
        if app.status != AppStatus.PUBLISHED.value:
            raise ValidateErrorException("只有已发布的应用才能共享到广场")

        # 3.处理标签
        if tags:
            # 如果提供了标签，使用提供的标签
            tag_list = [t.strip() for t in tags.split(',') if t.strip()]
            tag_list = sort_tags_by_priority(tag_list)
        else:
            # 如果没有提供标签，自动分配
            tag_list = TagAssignmentService.auto_assign_tags(app.name, app.description)

        # 4.更新应用为公开状态
        self.update(app, **{
            "is_public": True,
            "tags": tag_list,
            "published_at": datetime.now(UTC).replace(tzinfo=None),
        })

        logging.info(f"应用已共享到广场: app_id={app_id}, tags={tag_list}")
        return app

    def unshare_app_from_square(self, app_id: UUID, account: Account) -> App:
        """取消应用从广场的共享"""
        # 1.获取应用并校验权限
        app = self.db.session.query(App).filter(App.id == app_id).one_or_none()
        if not app:
            raise NotFoundException("应用不存在")

        if app.account_id != account.id:
            raise ForbiddenException("无权限操作该应用")

        # 2.更新应用为非公开状态
        self.update(app, **{
            "is_public": False,
            "published_at": None,
        })

        logging.info(f"应用已从广场取消共享: app_id={app_id}")
        return app

    def get_public_apps_with_page(
            self,
            req: GetPublicAppsWithPageReq,
            account: Account = None
    ) -> tuple[list[dict[str, Any]], Paginator]:
        """获取公共应用广场列表(支持标签、排序、搜索)"""
        # 1.构建分页器
        paginator = Paginator(db=self.db, req=req)

        # 2.构建筛选条件
        filters = [
            App.is_public == True,
            App.status == AppStatus.PUBLISHED.value,
        ]

        # 标签筛选 - 支持多选，OR关系
        if req.tags.data:
            tag_list = [t.strip() for t in req.tags.data.split(',') if t.strip()]
            if tag_list:
                # 使用PostgreSQL的JSONB包含操作符
                tag_filters = []
                for tag in tag_list:
                    tag_filters.append(App.tags.contains([tag]))
                filters.append(or_(*tag_filters))

        # 搜索词筛选
        if req.search_word.data:
            filters.append(
                or_(
                    App.name.ilike(f"%{req.search_word.data}%"),
                    App.description.ilike(f"%{req.search_word.data}%")
                )
            )

        # 3.执行查询
        favorite_count_subquery = (
            self.db.session.query(
                AppFavorite.app_id.label("app_id"),
                func.count(AppFavorite.id).label("favorite_count"),
            )
            .group_by(AppFavorite.app_id)
            .subquery()
        )
        query = (
            self.db.session.query(
                App,
                Account.name.label("creator_name"),
                Account.avatar.label("creator_avatar"),
                func.coalesce(favorite_count_subquery.c.favorite_count, 0).label("favorite_count"),
            )
            .join(Account, Account.id == App.account_id)
            .outerjoin(favorite_count_subquery, favorite_count_subquery.c.app_id == App.id)
            .filter(*filters)
        )

        # 4.根据排序规则让数据库优先裁剪用户应用，避免 query.all() 全量加载。
        sort_field_map = {
            "latest": App.published_at,
            "popular": App.view_count,
            "most_liked": App.like_count,
            "most_favorited": func.coalesce(favorite_count_subquery.c.favorite_count, 0),
            "most_forked": App.fork_count,
        }
        sort_field = sort_field_map.get(req.sort_by.data, App.published_at)
        query = query.order_by(sort_field.desc(), App.created_at.desc())

        total_user_apps = query.count()
        end = req.current_page.data * req.page_size.data
        user_rows = query.limit(end).all()

        liked_app_ids: set[UUID] = set()
        favorited_app_ids: set[UUID] = set()
        forked_app_ids: set[UUID] = set()

        # 先构建所有应用的ID集合（用于批量查询）
        all_app_ids = [app.id for app, _creator_name, _creator_avatar, _favorite_count in user_rows]

        if account and all_app_ids:
            liked_app_ids = {
                row[0]
                for row in self.db.session.query(AppLike.app_id).filter(
                    AppLike.account_id == account.id,
                    AppLike.app_id.in_(all_app_ids),
                ).all()
            }
            favorited_app_ids = {
                row[0]
                for row in self.db.session.query(AppFavorite.app_id).filter(
                    AppFavorite.account_id == account.id,
                    AppFavorite.app_id.in_(all_app_ids),
                ).all()
            }
            # 查询用户是否fork过这些应用（包括草稿状态）
            forked_app_ids = {
                row[0]
                for row in self.db.session.query(App.original_app_id).filter(
                    App.account_id == account.id,
                    App.original_app_id.in_(all_app_ids),
                    App.original_app_id.isnot(None),
                ).all()
            }

        # 5.构建用户共享应用数据
        user_app_list = []
        for app, creator_name, creator_avatar, favorite_count in user_rows:
            creator_name = creator_name or "未知用户"

            app_dict = {
                "id": str(app.id),
                "name": app.name,
                "icon": app.icon,
                "description": app.description,
                "tags": app.tags if app.tags else [],
                "view_count": app.view_count,
                "like_count": app.like_count,
                "fork_count": app.fork_count,
                "favorite_count": favorite_count,  # 添加收藏数
                "creator_name": creator_name,  # 添加发布者名称
                "creator_avatar": creator_avatar or "",  # 添加发布者头像
                "published_at": int(app.published_at.timestamp()) if app.published_at else 0,
                "created_at": int(app.created_at.timestamp()),
                "is_liked": False,
                "is_favorited": False,
                "is_forked": False,  # 是否已fork
            }

            # 如果用户已登录，使用批量查询结果设置点赞/收藏/fork状态。
            if account:
                app_dict["is_liked"] = app.id in liked_app_ids
                app_dict["is_favorited"] = app.id in favorited_app_ids
                app_dict["is_forked"] = app.id in forked_app_ids

            user_app_list.append(app_dict)

        # 6.手动分页
        total = total_user_apps
        start = (req.current_page.data - 1) * req.page_size.data
        page_end = start + req.page_size.data
        paginated_apps = user_app_list[start:page_end]

        # 7.更新分页器的总数与总页数
        if hasattr(paginator, "total_record"):
            paginator.total_record = total
        if hasattr(paginator, "total_page"):
            paginator.total_page = math.ceil(total / req.page_size.data) if req.page_size.data else 0

        # 兼容旧测试中的 _Paginator(total) 伪对象。
        if hasattr(paginator, "total"):
            paginator.total = total

        return paginated_apps, paginator

    def fork_public_app(self, app_id: str, account: Account) -> App:
        """Fork公共应用到个人空间"""
        # 1.解析应用ID并按用户共享应用处理
        try:
            app_uuid = UUID(app_id)
        except ValueError:
            raise NotFoundException("应用不存在")

        # 2.获取公共应用
        public_app = self.db.session.query(App).filter(
            App.id == app_uuid,
            App.is_public == True,
            App.status == AppStatus.PUBLISHED.value
        ).one_or_none()

        if not public_app:
            raise NotFoundException("公共应用不存在或未公开")

        # 3.增加浏览次数
        self.update(public_app, view_count=public_app.view_count + 1)

        # 4.获取应用的发布配置
        app_config = public_app.app_config
        if not app_config:
            raise FailException("应用配置不存在,无法Fork")

        # 5.复制应用基础信息
        app_dict = {
            "account_id": account.id,
            "name": f"{public_app.name} (副本)",
            "icon": public_app.icon,
            "description": public_app.description,
            "status": AppStatus.DRAFT.value,
            "tags": public_app.tags,
            "original_app_id": public_app.id,  # 记录原始应用ID
        }

        # 6.复制应用配置
        config_dict = {
            "model_config": app_config.model_config,
            "dialog_round": app_config.dialog_round,
            "preset_prompt": app_config.preset_prompt,
            "tools": app_config.tools,
            "workflows": app_config.workflows,
            "retrieval_config": app_config.retrieval_config,
            "long_term_memory": app_config.long_term_memory,
            "opening_statement": app_config.opening_statement,
            "opening_questions": app_config.opening_questions,
            "speech_to_text": app_config.speech_to_text,
            "text_to_speech": app_config.text_to_speech,
            "suggested_after_answer": app_config.suggested_after_answer,
            "review_config": app_config.review_config,
        }

        # 7.开启数据库自动提交上下文
        with self.db.auto_commit():
            # 8.创建新应用
            new_app = App(**app_dict)
            self.db.session.add(new_app)
            self.db.session.flush()

            # 9.创建草稿配置
            new_draft_config = AppConfigVersion(
                **config_dict,
                app_id=new_app.id,
                version=0,
                config_type="draft",
                datasets=[]  # 草稿配置需要datasets字段
            )
            self.db.session.add(new_draft_config)
            self.db.session.flush()

            # 10.更新应用的草稿配置ID
            new_app.draft_app_config_id = new_draft_config.id

            # 11.复制知识库关联(如果有)
            dataset_joins = app_config.app_dataset_joins
            copied_dataset_ids: set[UUID] = set()
            for join in dataset_joins:
                # 仅复制关联关系，不复制知识库数据本体。
                if join.dataset_id in copied_dataset_ids:
                    continue
                copied_dataset_ids.add(join.dataset_id)
                self.db.session.add(
                    AppDatasetJoin(
                        app_id=new_app.id,
                        dataset_id=join.dataset_id,
                        )
                )

        # 12.增加原应用的Fork计数
        self.update(public_app, fork_count=public_app.fork_count + 1)

        logging.info(f"应用已Fork: original_app_id={app_id}, new_app_id={new_app.id}, account_id={account.id}")
        return new_app

    def like_app(self, app_id: UUID, account: Account) -> dict[str, Any]:
        """点赞应用"""
        # 1.获取应用
        app = self.db.session.query(App).filter(
            App.id == app_id,
            App.is_public == True
        ).one_or_none()

        if not app:
            raise NotFoundException("应用不存在或未公开")

        # 2.检查是否已点赞
        existing_like = self.db.session.query(AppLike).filter(
            AppLike.app_id == app_id,
            AppLike.account_id == account.id
        ).one_or_none()

        if existing_like:
            # 已点赞,则取消点赞
            self.db.session.delete(existing_like)
            self.update(app, like_count=max(0, app.like_count - 1))
            self.db.session.commit()
            return {"is_liked": False, "like_count": app.like_count}
        else:
            # 未点赞,则添加点赞
            new_like = AppLike(app_id=app_id, account_id=account.id)
            self.db.session.add(new_like)
            self.update(app, like_count=app.like_count + 1)
            self.db.session.commit()
            return {"is_liked": True, "like_count": app.like_count}

    def favorite_app(self, app_id: UUID, account: Account) -> dict[str, Any]:
        """收藏应用"""
        # 1.获取应用
        app = self.db.session.query(App).filter(
            App.id == app_id,
            App.is_public == True
        ).one_or_none()

        if not app:
            raise NotFoundException("应用不存在或未公开")

        # 2.检查是否已收藏
        existing_favorite = self.db.session.query(AppFavorite).filter(
            AppFavorite.app_id == app_id,
            AppFavorite.account_id == account.id
        ).one_or_none()

        if existing_favorite:
            # 已收藏,则取消收藏
            self.db.session.delete(existing_favorite)
            self.db.session.commit()
            return {"is_favorited": False}
        else:
            # 未收藏,则添加收藏
            new_favorite = AppFavorite(app_id=app_id, account_id=account.id)
            self.db.session.add(new_favorite)
            self.db.session.commit()
            return {"is_favorited": True}

    def get_my_favorites(self, account: Account) -> list[App]:
        """获取我的收藏列表"""
        favorites = self.db.session.query(AppFavorite).filter(
            AppFavorite.account_id == account.id
        ).all()

        app_ids = [f.app_id for f in favorites]
        apps = self.db.session.query(App).filter(
            App.id.in_(app_ids),
            App.is_public == True
        ).all()

        return apps

    def get_public_app_detail(self, app_id: str, account: Account = None) -> dict[str, Any]:
        """获取公共应用详情（包括配置信息）"""
        # 1.查询用户共享应用
        try:
            app_uuid = UUID(app_id)
        except ValueError:
            raise NotFoundException("应用不存在")

        # 2.获取公共应用
        app = self.db.session.query(App).filter(
            App.id == app_uuid,
            App.is_public == True,
            App.status == AppStatus.PUBLISHED.value
        ).one_or_none()

        if not app:
            raise NotFoundException("公共应用不存在或未公开")

        # 3.增加浏览次数
        self.update(app, view_count=app.view_count + 1)

        # 4.获取发布者信息
        creator = self.db.session.query(Account).filter(Account.id == app.account_id).one_or_none()
        creator_name = creator.name if creator else "未知用户"

        # 5.计算收藏数
        favorite_count = self.db.session.query(func.count(AppFavorite.id)).filter(
            AppFavorite.app_id == app.id
        ).scalar() or 0

        # 6.构建应用详情
        app_detail = {
            "id": str(app.id),
            "name": app.name,
            "icon": app.icon,
            "description": app.description,
            "tags": app.tags,
            "status": app.status,
            "is_public": app.is_public,
            "view_count": app.view_count,
            "like_count": app.like_count,
            "fork_count": app.fork_count,
            "favorite_count": favorite_count,
            "creator_name": creator_name,
            "published_at": int(app.published_at.timestamp()) if app.published_at else 0,
            "created_at": int(app.created_at.timestamp()),
            "is_liked": False,
            "is_favorited": False,
            "is_forked": False,  # 是否已fork
        }

        # 7.如果用户已登录，查询用户的点赞、收藏和fork状态
        if account:
            is_liked = self.db.session.query(AppLike).filter(
                AppLike.app_id == app.id,
                AppLike.account_id == account.id
            ).one_or_none() is not None

            is_favorited = self.db.session.query(AppFavorite).filter(
                AppFavorite.app_id == app.id,
                AppFavorite.account_id == account.id
            ).one_or_none() is not None

            # 查询用户是否fork过该应用（包括草稿状态）
            is_forked = self.db.session.query(App).filter(
                App.account_id == account.id,
                App.original_app_id == app.id,
                App.original_app_id.isnot(None),
            ).first() is not None

            app_detail["is_liked"] = is_liked
            app_detail["is_favorited"] = is_favorited
            app_detail["is_forked"] = is_forked

        # 8.获取应用配置信息
        app_config = app.app_config
        if app_config:
            app_detail["draft_app_config"] = {
                "model_config": app_config.model_config,
                "dialog_round": app_config.dialog_round,
                "preset_prompt": app_config.preset_prompt,
                "tools": self._enrich_tools(app_config.tools),  # 填充完整的 tool 信息
                "workflows": self._enrich_workflows(app_config.workflows),
                "datasets": [],  # 公共应用不暴露知识库详情
                "retrieval_config": app_config.retrieval_config,
                "long_term_memory": app_config.long_term_memory,
                "opening_statement": app_config.opening_statement,
                "opening_questions": app_config.opening_questions,
                "speech_to_text": app_config.speech_to_text,
                "text_to_speech": app_config.text_to_speech,
                "suggested_after_answer": app_config.suggested_after_answer,
                "review_config": app_config.review_config,
            }

        return app_detail

    def get_public_app_analysis(self, app_id: str, account: Account | None) -> dict:
        """获取公共应用的统计分析数据

        Args:
            app_id: 应用ID
            account: 账号信息（可选，未登录时为None）

        Returns:
            统计分析数据字典
        """
        from internal.service.analysis_service import AnalysisService
        from datetime import datetime, timedelta
        from uuid import UUID

        # 1.解析应用ID并查询公共应用（不校验权限）
        try:
            app_uuid = UUID(app_id)
        except ValueError:
            raise NotFoundException("公共应用不存在")

        app = self.db.session.query(App).filter(
            App.id == app_uuid,
            App.is_public == True,
            App.status == AppStatus.PUBLISHED.value
        ).one_or_none()

        if not app:
            raise NotFoundException("公共应用不存在")

        # 2.获取 AnalysisService 实例
        from app.http.module import injector
        analysis_service = injector.get(AnalysisService)

        # 3.获取当前时间、午夜时间、7天前时间、14天前的时间
        now = datetime.now()
        today_midnight = datetime.combine(now, datetime.min.time())
        seven_days_ago = today_midnight - timedelta(days=7)
        fourteen_days_ago = today_midnight - timedelta(days=14)

        # 4.查询消息表最近7天(到当前时间)，以及最近14-7天的数据
        seven_days_messages = analysis_service.get_messages_by_time_range(app, seven_days_ago, now)
        fourteen_days_messages = analysis_service.get_messages_by_time_range(app, fourteen_days_ago, seven_days_ago)

        # 5.计算5个概念指标
        seven_overview_indicators = analysis_service.calculate_overview_indicators_by_messages(seven_days_messages)
        fourteen_overview_indicators = analysis_service.calculate_overview_indicators_by_messages(fourteen_days_messages)

        # 6.统计环比数据
        pop = analysis_service.calculate_pop_by_overview_indicators(seven_overview_indicators, fourteen_overview_indicators)

        # 7.计算4个指标对应的趋势
        trend = analysis_service.calculate_trend_by_messages(today_midnight, 7, seven_days_messages)

        # 8.定义5个指标字段名称
        fields = [
            "total_messages", "active_accounts", "avg_of_conversation_messages",
            "token_output_rate", "cost_consumption",
        ]

        # 9.构建应用分析字典（与 AnalysisService 返回格式一致）
        result = {
            **trend,  # 包含 *_trend 字段
            **{
                field: {
                    "data": seven_overview_indicators.get(field),
                    "pop": pop.get(field),
                } for field in fields
            }
        }

        return result
