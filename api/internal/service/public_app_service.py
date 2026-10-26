"""公共应用服务 - 处理应用广场相关逻辑"""
import logging
import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from injector import inject
from sqlalchemy import or_

from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.entity.app_entity import AppStatus
from internal.entity.workflow_entity import WorkflowStatus
from internal.entity.tag_entity import sort_tags_by_priority
from internal.lib.helper import datetime_to_timestamp, utc_now_naive
from internal.task.app_task import sync_public_app_registry
from internal.service.tag_assignment_service import TagAssignmentService
from internal.exception import NotFoundException, ForbiddenException, ValidateErrorException, FailException
from internal.model import (
    App,
    AppConfigVersion,
    AppDatasetJoin,
    Account,
    ApiToolProvider,
    ApiTool,
    Workflow,
)
from internal.schema.public_app_schema import GetPublicAppsWithPageReq
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .app_config_service import AppConfigService
from .language_model_service import LanguageModelService
from .public_agent_registry_service import PublicAgentRegistryService


@inject
@dataclass
class PublicAppService(BaseService):
    """公共应用服务"""
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager
    app_config_service: AppConfigService | None = None
    language_model_service: LanguageModelService | None = None
    public_agent_registry_service: PublicAgentRegistryService | None = None

    @classmethod
    def _enqueue_public_app_registry_sync(cls, app_id: UUID) -> None:
        """后台同步公共Agent索引，失败时仅记录日志，不阻塞分享主流程。"""
        try:
            sync_public_app_registry.delay(str(app_id))
        except Exception:
            logging.exception("公共Agent索引同步任务入队失败: app_id=%s", app_id)

    @staticmethod
    def _resolve_public_app_tags(app: App) -> list[str]:
        """优先使用已保存标签；缺失时仅做轻量关键词兜底。"""
        tags = list(getattr(app, "tags", []) or [])
        if tags:
            return sort_tags_by_priority(tags)
        tags = TagAssignmentService.match_tags_by_keywords(app.name, app.description)
        return tags if tags else ["other"]

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
            if not tag_list:
                tag_list = ["other"]
        else:
            # 如果没有提供标签，使用轻量关键词兜底，避免读写链路反复触发模型
            tag_list = TagAssignmentService.match_tags_by_keywords(app.name, app.description)
            if not tag_list:
                tag_list = ["other"]

        # 4.更新应用为公开状态
        self.update(app, **{
            "is_public": True,
            "tags": tag_list,
            "published_at": utc_now_naive(),
        })

        if self.public_agent_registry_service:
            self._enqueue_public_app_registry_sync(app.id)
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

        if self.public_agent_registry_service:
            self._enqueue_public_app_registry_sync(app.id)
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
        requested_tags = [t.strip() for t in req.tags.data.split(',') if t.strip()] if req.tags.data else []

        # 搜索词筛选
        if req.search_word.data:
            filters.append(
                or_(
                    App.name.ilike(f"%{req.search_word.data}%"),
                    App.description.ilike(f"%{req.search_word.data}%")
                )
            )

        if requested_tags:
            filters.append(or_(*[App.tags.contains([tag]) for tag in requested_tags]))

        query = (
            self.db.session.query(
                App,
                Account.name.label("creator_name"),
                Account.avatar.label("creator_avatar"),
            )
            .join(Account, Account.id == App.account_id)
            .filter(*filters)
            .order_by(App.published_at.desc(), App.created_at.desc())
        )

        user_rows = paginator.paginate(query)

        forked_app_ids: set[UUID] = set()

        # 先构建所有应用的ID集合（用于批量查询）
        all_app_ids = [app.id for app, _creator_name, _creator_avatar in user_rows]

        if account and all_app_ids:
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
        for app, creator_name, creator_avatar in user_rows:
            creator_name = creator_name or "未知用户"
            resolved_tags = self._resolve_public_app_tags(app)

            app_dict = {
                "id": str(app.id),
                "name": app.name,
                "icon": app.icon,
                "description": app.description,
                "tags": resolved_tags,
                "creator_name": creator_name,  # 添加发布者名称
                "creator_avatar": creator_avatar or "",  # 添加发布者头像
                "published_at": datetime_to_timestamp(app.published_at),
                "created_at": datetime_to_timestamp(app.created_at),
                "is_forked": False,  # 是否已fork
            }

            # 如果用户已登录，使用批量查询结果设置点赞/收藏/fork状态。
            if account:
                app_dict["is_forked"] = app.id in forked_app_ids

            user_app_list.append(app_dict)

        # 6.分页器已经在数据库层完成切片，这里直接返回当前页结果
        total = getattr(paginator, "total_record", len(user_app_list))
        paginated_apps = user_app_list

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

        # 3.获取应用的发布配置
        app_config = public_app.app_config
        if not app_config:
            raise FailException("应用配置不存在,无法Fork")

        # 4.复制应用基础信息
        app_dict = {
            "account_id": account.id,
            "name": f"{public_app.name} (副本)",
            "icon": public_app.icon,
            "description": public_app.description,
            "status": AppStatus.DRAFT.value,
            "tags": self._resolve_public_app_tags(public_app),
            "original_app_id": public_app.id,  # 记录原始应用ID
        }

        # 5.复制应用配置
        config_dict = {
            "model_config": app_config.model_config,
            "dialog_round": app_config.dialog_round,
            "preset_prompt": app_config.preset_prompt,
            "tools": app_config.tools,
            "mcp_bindings": getattr(app_config, "mcp_bindings", []),
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

        # 6.开启数据库自动提交上下文
        with self.db.auto_commit():
            # 7.创建新应用
            new_app = App(**app_dict)
            self.db.session.add(new_app)
            self.db.session.flush()

            # 8.创建草稿配置
            new_draft_config = AppConfigVersion(
                **config_dict,
                app_id=new_app.id,
                version=0,
                config_type="draft",
                datasets=[]  # 草稿配置需要datasets字段
            )
            self.db.session.add(new_draft_config)
            self.db.session.flush()

            # 9.更新应用的草稿配置ID
            new_app.draft_app_config_id = new_draft_config.id

            # 10.复制知识库关联(如果有)
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

        logging.info(f"应用已Fork: original_app_id={app_id}, new_app_id={new_app.id}, account_id={account.id}")
        return new_app

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

        # 3.获取发布者信息
        creator = self.db.session.query(Account).filter(Account.id == app.account_id).one_or_none()
        creator_name = creator.name if creator else "未知用户"
        creator_avatar = getattr(creator, "avatar", "") if creator else ""

        # 4.构建应用详情
        app_detail = {
            "id": str(app.id),
            "name": app.name,
            "icon": app.icon,
            "description": app.description,
            "tags": self._resolve_public_app_tags(app),
            "status": app.status,
            "is_public": app.is_public,
            "creator_name": creator_name,
            "creator_avatar": creator_avatar,
            "published_at": datetime_to_timestamp(app.published_at),
            "created_at": datetime_to_timestamp(app.created_at),
            "is_forked": False,  # 是否已fork
        }

        # 5.如果用户已登录，查询用户的 fork 状态
        if account:
            # 查询用户是否fork过该应用（包括草稿状态）
            is_forked = self.db.session.query(App).filter(
                App.account_id == account.id,
                App.original_app_id == app.id,
                App.original_app_id.isnot(None),
            ).first() is not None

            app_detail["is_forked"] = is_forked

        # 6.获取应用配置信息
        app_config = app.app_config
        if app_config:
            agent_bindings = []
            if self.app_config_service is not None:
                agent_bindings, _ = self.app_config_service.process_and_validate_agent_bindings(
                    getattr(app_config, "agent_bindings", []),
                    current_account_id=None,
                    current_app_id=app.id,
                )
            else:
                agent_bindings = [
                    {
                        "app_id": str(binding.get("app_id", "")).strip(),
                        "invoke_mode": str(binding.get("invoke_mode", "tool")).strip().lower() or "tool",
                    }
                    for binding in getattr(app_config, "agent_bindings", [])
                    if isinstance(binding, dict) and str(binding.get("app_id", "")).strip()
                ]

            app_detail["draft_app_config"] = {
                "model_config": app_config.model_config,
                "capabilities": (
                    self.language_model_service.describe_runtime_capabilities(
                        app_config.model_config,
                        entrypoint=LanguageModelService.ENTRYPOINT_PUBLIC_A2A,
                        allow_image_input=False,
                    )
                    if self.language_model_service is not None
                    else {}
                ),
                "dialog_round": app_config.dialog_round,
                "preset_prompt": app_config.preset_prompt,
                "tools": self._enrich_tools(app_config.tools),  # 填充完整的 tool 信息
                "mcp_bindings": getattr(app_config, "mcp_bindings", []),
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
