import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, Generator, TYPE_CHECKING
from uuid import UUID, uuid4
from flask import Flask, current_app, has_app_context
from injector import inject
from langchain_core.messages import AIMessage, trim_messages
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
from internal.entity.audio_entity import ALLOWED_AUDIO_VOICES
from redis import Redis
from sqlalchemy import func, desc
from sqlalchemy.orm import joinedload, selectinload
from internal.core.agent.agents import FunctionCallAgent, AgentQueueManager, ReACTAgent, DeepThinkingAgent
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.agent.usage_utils import summarize_agent_thoughts
from internal.core.language_model import LanguageModelManager
from internal.core.memory import TokenBufferMemory
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.entity.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
from internal.entity.app_entity import AppStatus, AppConfigType, DEFAULT_APP_CONFIG
from internal.entity.tag_entity import sort_tags_by_priority
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from internal.exception import NotFoundException, ForbiddenException, ValidateErrorException, FailException
from internal.lib.helper import remove_fields, get_value_type, generate_random_string
from internal.model import (
    App,
    Account,
    AppConfigVersion,
    ApiTool,
    Dataset,
    AppConfig,
    AppDatasetJoin,
    Conversation,
    Message, Workflow,
)
from internal.schema.app_schema import (
    CreateAppReq,
    DebugChatReq,
    GetAppsWithPageReq,
    GetPublishHistoriesWithPageReq,
    GetDebugConversationMessagesWithPageReq,
)
from internal.task.app_task import prewarm_mcp_tool_snapshots, sync_public_app_registry
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .app_config_service import AppConfigService, call_config_loader
from .base_service import BaseService
from .conversation_service import ConversationService
from .cos_service import CosService
from .language_model_service import LanguageModelService
from .public_agent_registry_service import PublicAgentRegistryService
from .retrieval_service import RetrievalService
from .icon_generator_service import IconGeneratorService
from .skill_service import SkillService
from .tag_assignment_service import TagAssignmentService
from ..core.language_model.entities.model_entity import ModelParameterType, ModelFeature
from ..core.language_model.providers.deepseek.chat import Chat
from ..entity.workflow_entity import WorkflowStatus


@inject
@dataclass
class AppService(BaseService):
    """应用服务逻辑"""
    db: SQLAlchemy
    redis_client: Redis
    cos_service: CosService
    retrieval_service: RetrievalService
    app_config_service: AppConfigService
    api_provider_manager: ApiProviderManager
    conversation_service: ConversationService
    language_model_manager: LanguageModelManager
    language_model_service: LanguageModelService
    builtin_provider_manager: BuiltinProviderManager
    icon_generator_service: IconGeneratorService
    public_agent_registry_service: PublicAgentRegistryService | None = None
    AUTO_CREATE_DEFAULT_TOOLS = [
        {
            "type": "builtin_tool",
            "provider_id": "google",
            "tool_id": "google_serper",
            "params": {},
        },
        {
            "type": "builtin_tool",
            "provider_id": "gaode",
            "tool_id": "gaode_weather",
            "params": {},
        },
        {
            "type": "builtin_tool",
            "provider_id": "qwen",
            "tool_id": "qwen_image_text_to_image",
            "params": {
                "image_size": "1328x1328",
                "num_inference_steps": 50,
                "cfg": 4.0,
            },
        },
    ]

    @classmethod
    def _enqueue_public_app_registry_sync(cls, app_id: UUID) -> None:
        """后台同步公共Agent索引，失败时仅记录日志，不阻塞主流程。"""
        try:
            normalized_app_id = str(app_id)
            apply_async = getattr(sync_public_app_registry, "apply_async", None)
            if callable(apply_async):
                apply_async(
                    args=(normalized_app_id,),
                    ignore_result=True,
                    retry=False,
                )
                return

            sync_public_app_registry.delay(normalized_app_id)
        except Exception:
            logging.exception("公共Agent索引同步任务入队失败: app_id=%s", app_id)

    @classmethod
    def _enqueue_mcp_tool_snapshot_prewarm(cls, app_id: UUID, config_type: str) -> None:
        """后台预热 MCP 工具快照，失败时仅记录日志，不阻塞主流程。"""
        try:
            normalized_app_id = str(app_id)
            normalized_config_type = str(config_type)
            apply_async = getattr(prewarm_mcp_tool_snapshots, "apply_async", None)
            if callable(apply_async):
                apply_async(
                    args=(normalized_app_id, normalized_config_type),
                    ignore_result=True,
                    retry=False,
                )
                return

            prewarm_mcp_tool_snapshots.delay(normalized_app_id, normalized_config_type)
        except Exception:
            logging.exception(
                "MCP 工具快照预热任务入队失败: app_id=%s, config_type=%s",
                app_id,
                config_type,
            )

    def _sync_public_app_registry_after_unpublish(self, app_id: UUID) -> None:
        """取消发布后优先执行本地索引移除，失败时再退回异步任务同步。"""
        if not self.public_agent_registry_service:
            return

        remove_public_app = getattr(self.public_agent_registry_service, "remove_public_app", None)
        if callable(remove_public_app):
            try:
                remove_public_app(app_id)
                return
            except Exception:
                logging.exception("公共Agent索引移除失败，改为异步同步: app_id=%s", app_id)

        self._enqueue_public_app_registry_sync(app_id)

    def refresh_mcp_tool_snapshots(self, app_id: UUID, config_type: str) -> list[dict[str, Any]]:
        """根据应用配置类型刷新 MCP 工具快照，供后台任务调用。"""
        app = self.get(App, app_id)
        if not app:
            raise NotFoundException("该应用不存在，请核实后重试")

        normalized_config_type = str(config_type).strip().lower()
        if normalized_config_type == AppConfigType.DRAFT.value:
            target_config = app.draft_app_config
        elif normalized_config_type == AppConfigType.PUBLISHED.value:
            target_config = app.app_config
        else:
            raise FailException("MCP快照刷新配置类型错误")

        if not target_config:
            return []

        refreshed_snapshots = self.app_config_service.refresh_mcp_tool_snapshots(
            getattr(target_config, "mcp_bindings", []),
            getattr(target_config, "mcp_tool_snapshots", []),
        )
        if getattr(target_config, "mcp_tool_snapshots", []) != refreshed_snapshots:
            self.update(
                target_config,
                updated_at=datetime.now(UTC),
                mcp_tool_snapshots=refreshed_snapshots,
            )

        return refreshed_snapshots

    @classmethod
    def _normalize_opening_questions(cls, questions: list[Any]) -> list[str]:
        """规范化开场建议问题并确保最多返回3条有效内容"""
        normalized_questions = []

        # 1.清理无效问题并去重
        for question in questions:
            if not isinstance(question, str):
                continue
            question = question.strip()
            if not question:
                continue
            if question in normalized_questions:
                continue
            normalized_questions.append(question)
            if len(normalized_questions) >= 3:
                break

        # 2.不足3条时补充兜底问题，保证首屏体验完整
        fallback_questions = [
            "这个Agent可以帮我做什么？",
            "我先提供哪些信息会更高效？",
            "可以先给我一个示例任务吗？",
        ]
        for fallback_question in fallback_questions:
            if len(normalized_questions) >= 3:
                break
            if fallback_question in normalized_questions:
                continue
            normalized_questions.append(fallback_question)

        return normalized_questions

    def _get_skill_service(self) -> SkillService:
        """获取技能服务，兼容测试里传入的简化 app_config_service。"""
        skill_service = getattr(self.app_config_service, "skill_service", None)
        if skill_service is not None:
            return skill_service
        return SkillService(self.db)

    def auto_create_app(self, name: str, description: str, account_id: UUID) -> App:
        """根据传递的应用名称、描述、账号id利用AI创建一个Agent智能体"""
        name = (name or "").strip()
        description = (description or "").strip()

        # 1.创建LLM，用于生成icon提示与预设提示词
        llm = Chat(
            model="deepseek-chat",
            temperature=0.8,
            features=[ModelFeature.TOOL_CALL.value, ModelFeature.AGENT_THOUGHT.value],
            metadata={},
        )

        # 2.生成预设prompt链
        generate_preset_prompt_chain = ChatPromptTemplate.from_messages([
            ("system", OPTIMIZE_PROMPT_TEMPLATE),
            ("human", "应用名称: {name}\n\n应用描述: {description}")
        ]) | llm | StrOutputParser()

        app_config = {
            "preset_prompt": generate_preset_prompt_chain.invoke({
                "name": name,
                "description": description,
            })
        }

        # 5.1 自动生成对话开场白与开场建议问题
        opening_statement = (description or "").strip()
        if not opening_statement:
            opening_statement = f"你好，我是{name}，很高兴为你服务。"
        if len(opening_statement) > 2000:
            opening_statement = opening_statement[:2000]

        opening_questions = []
        try:
            # 使用统一的建议问题能力生成开场建议问题，避免额外维护提示词模板
            histories = (
                f"Human: 我想创建一个名为{name}的Agent，功能描述是：{description}\n"
                f"AI: Agent已创建完成，请开始与我对话。"
            )
            opening_questions = self.conversation_service.generate_suggested_questions(histories)
        except Exception as e:
            logging.exception(
                f"自动创建Agent时生成开场建议问题失败, name: {name}, 错误信息: {str(e)}"
            )
        opening_questions = self._normalize_opening_questions(
            opening_questions if isinstance(opening_questions, list) else []
        )
        default_tools = [
            {
                "type": tool["type"],
                "provider_id": tool["provider_id"],
                "tool_id": tool["tool_id"],
                "params": dict(tool["params"]),
            }
            for tool in self.AUTO_CREATE_DEFAULT_TOOLS
        ]

        # 6.使用共享图标服务生成并上传应用图标；图标生成失败不应阻断Agent创建。
        try:
            icon = self.icon_generator_service.generate_icon(
                name=name,
                description=description or "",
            )
        except Exception:
            logging.exception("自动创建Agent时生成图标失败，使用默认图标: name=%s", name)
            icon = self._generate_default_icon(name)

        account = self.db.session.query(Account).get(account_id)

        # 7.开启数据库自动提交上下文
        with self.db.auto_commit():
            # 8.创建应用记录并刷新数据，从而可以拿到应用id
            app = App(
                account_id=account.id,
                name=name,
                icon=icon,
                description=description,
                status=AppStatus.DRAFT.value
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 9.添加草稿记录
            app_config_version = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT.value,
                **{
                    **DEFAULT_APP_CONFIG,
                    "preset_prompt": app_config.get("preset_prompt", ""),
                    "tools": default_tools,
                    "opening_statement": opening_statement,
                    "opening_questions": opening_questions,
                    # 显式覆盖，确保辅助Agent自动创建场景始终开启语音体验
                    "speech_to_text": {"enable": True},
                    "text_to_speech": {"enable": True, "voice": "alex", "auto_play": True},
                }
            )
            self.db.session.add(app_config_version)
            self.db.session.flush()

            # 10.更新应用配置id
            app.draft_app_config_id = app_config_version.id

        # 11.返回创建的应用
        return app

    def create_app(self, req: CreateAppReq, account: Account) -> App:
        """创建Agent应用服务"""
        # 1. 如果用户未提供图标，自动生成图标
        icon_url = req.icon.data
        if not icon_url:
            try:
                logging.info(f"用户未提供图标，自动生成图标: name={req.name.data}")
                icon_url = self.icon_generator_service.generate_icon(
                    name=req.name.data,
                    description=req.description.data or ""
                )
                logging.info(f"自动生成图标成功: {icon_url}")
            except Exception as e:
                logging.error(f"自动生成图标失败: {str(e)}")
                # 如果生成失败，使用默认图标 - 使用一个彩色的SVG图标
                icon_url = self._generate_default_icon(req.name.data)

        # 2.开启数据库自动提交上下文
        with self.db.auto_commit():
            # 3.创建应用记录，并刷新数据，从而可以拿到应用id
            app = App(
                account_id=account.id,
                name=req.name.data,
                icon=icon_url,
                description=req.description.data,
                status=AppStatus.DRAFT.value,
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 4.添加草稿记录
            app_config_version = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT.value,
                **DEFAULT_APP_CONFIG,
            )
            self.db.session.add(app_config_version)
            self.db.session.flush()

            # 5.为应用添加草稿配置id
            app.draft_app_config_id = app_config_version.id

        # 6.返回创建的应用记录
        return app

    def get_app(self, app_id: UUID, account: Account) -> App:
        """根据传递的id获取应用的基础信息"""
        # 1.查询数据库获取应用基础信息
        app = self.get(App, app_id)

        # 2.判断应用是否存在
        if not app:
            raise NotFoundException("该应用不存在，请核实后重试")

        # 3.判断当前账号是否有权限访问该应用
        if app.account_id != account.id:
            raise ForbiddenException("当前账号无权限访问该应用，请核实后尝试")

        return app

    def delete_app(self, app_id: UUID, account: Account):
        app = self.get_app(app_id, account)
        self.delete(app)
        return app

    def update_app(self, app_id: UUID, account: Account, **kwargs) -> App:
        """根据传递的应用id+账号+信息,更新指定的应用"""
        app = self.get_app(app_id, account)
        self.update(app, **kwargs)
        return app

    def copy_app(self, app_id: UUID, account: Account) -> App:
        """根据传递的应用id,拷贝Agent相关信息并创建一个新Agent"""
        # 1.获取App+草稿配置 并校验权限
        app = self.get_app(app_id, account)
        draft_app_config = app.draft_app_config

        # 2.将数据转换为字典并剔除无用数据
        app_dict = app.__dict__.copy()
        draft_app_config_dict = draft_app_config.__dict__.copy()

        # 3.剔除无用字段
        app_remove_fields = [
            "id", "app_config_id", "draft_app_config_id", "debug_conversation_id", "status",
            "updated_at", "created_at", "_sa_instance_state",
        ]
        draft_app_config_remove_fields = [
            "id", "app_id", "version", "updated_at", "created_at", "_sa_instance_state",
        ]
        remove_fields(app_dict, app_remove_fields)
        remove_fields(draft_app_config_dict, draft_app_config_remove_fields)

        # 4.开启数据库自动提交上下文
        with self.db.auto_commit():
            # 5.创建一个新的应用记录
            new_app = App(**app_dict, status=AppStatus.DRAFT.value)
            self.db.session.add(new_app)
            self.db.session.flush()

            # 6.添加草稿配置
            new_draft_app_config = AppConfigVersion(
                **draft_app_config_dict,
                app_id=new_app.id,
                version=0
            )
            self.db.session.add(new_draft_app_config)
            self.db.session.flush()

            # 7.更新应用的草稿配置id
            new_app.draft_app_config_id = new_draft_app_config.id

        # 8.返回创建好的新应用
        return new_app

    def get_apps_with_page(self, req: GetAppsWithPageReq, account: Account) -> tuple[list[App], Paginator]:
        """根据传递的分页参数获取当前登录账号下的应用分页列表数据"""
        # 1.构建分页器
        paginator = Paginator(db=self.db, req=req)

        # 2.构建筛选条件
        filters = [App.account_id == account.id]
        if req.search_word.data:
            filters.append(App.name.ilike(f"%{req.search_word.data}%"))
        if getattr(req, "published_only", None) and req.published_only.data:
            filters.append(App.status == AppStatus.PUBLISHED.value)

        # 3.执行分页操作
        apps = paginator.paginate(
            self.db.session.query(App).filter(*filters).order_by(desc("created_at"))
        )

        return apps, paginator

    def get_draft_app_config(
        self,
        app_id: UUID,
        account: Account,
        persist_changes: bool = True,
    ) -> dict[str, Any]:
        """根据传递的应用id，获取指定的应用草稿配置信息"""
        app = self.get_app(app_id, account)
        draft_app_config = self.app_config_service.get_draft_app_config(app)
        if hasattr(self.language_model_service, "describe_runtime_capabilities"):
            draft_app_config["capabilities"] = self.language_model_service.describe_runtime_capabilities(
                draft_app_config.get("model_config", {}),
                entrypoint=LanguageModelService.ENTRYPOINT_DEBUGGER,
            )
        return draft_app_config

    def update_draft_app_config(
            self,
            app_id: UUID,
            draft_app_config: dict[str, Any],
            account: Account,
    ) -> AppConfigVersion:
        """根据传递的应用id+草稿配置修改指定应用的最新草稿"""
        # 1.获取应用信息并校验
        app = self.get_app(app_id, account)

        # 2.校验传递的草稿配置信息
        draft_app_config = self._validate_draft_app_config(draft_app_config, account, app_id)

        # 3.获取当前应用的最新草稿信息
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # todo:由于目前使用server_onupdate，所以该字段暂时需要手动传递
            updated_at=datetime.now(UTC),
            **draft_app_config,
        )

        prepared_mcp_tool_snapshots = self.app_config_service.prepare_mcp_tool_snapshots(
            getattr(draft_app_config_record, "mcp_bindings", []),
            getattr(draft_app_config_record, "mcp_tool_snapshots", []),
        )
        if getattr(draft_app_config_record, "mcp_tool_snapshots", []) != prepared_mcp_tool_snapshots:
            self.update(
                draft_app_config_record,
                updated_at=datetime.now(UTC),
                mcp_tool_snapshots=prepared_mcp_tool_snapshots,
            )

        self._enqueue_mcp_tool_snapshot_prewarm(app.id, AppConfigType.DRAFT.value)

        return draft_app_config_record

    def publish_draft_app_config(self, app_id: UUID, account: Account, share_to_square: bool = True) -> App:
        """根据传递的应用id+账号，发布/更新指定的应用草稿配置为运行时配置

        Args:
            app_id: 应用ID
            account: 账号信息
            share_to_square: 是否同时分享到应用广场，默认为True（保持向后兼容）
        """
        # 1.获取应用的信息以及草稿信息
        app = self.get_app(app_id, account)
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 2.创建应用运行配置（在这里暂时不删除历史的运行配置）
        app_config = self.create(
            AppConfig,
            app_id=app_id,
            model_config=draft_app_config["model_config"],
            dialog_round=draft_app_config["dialog_round"],
            preset_prompt=draft_app_config["preset_prompt"],
            tools=[
                {
                    "type": tool["type"],
                    "provider_id": tool["provider"]["id"],
                    "tool_id": tool["tool"]["name"],
                    "params": tool["tool"]["params"],
                }
                for tool in draft_app_config["tools"]
            ],
            mcp_bindings=draft_app_config.get("mcp_bindings", []),
            mcp_tool_snapshots=draft_app_config.get("mcp_tool_snapshots", []),
            skills=[{"skill_id": skill["skill_id"]} for skill in draft_app_config.get("skills", [])],
            agent_bindings=draft_app_config.get("agent_bindings", []),
            workflows=[workflow["id"] for workflow in draft_app_config["workflows"]],
            retrieval_config=draft_app_config["retrieval_config"],
            long_term_memory=draft_app_config["long_term_memory"],
            opening_statement=draft_app_config["opening_statement"],
            opening_questions=draft_app_config["opening_questions"],
            speech_to_text=draft_app_config["speech_to_text"],
            text_to_speech=draft_app_config["text_to_speech"],
            suggested_after_answer=draft_app_config["suggested_after_answer"],
            review_config=draft_app_config["review_config"],
        )

        # 3.更新应用关联的运行时配置、状态
        update_data = {
            "app_config_id": app_config.id,
            "status": AppStatus.PUBLISHED.value,
        }

        # 如果指定分享到广场，则设置 is_public
        if share_to_square:
            update_data["is_public"] = True
            existing_tags = list(getattr(app, "tags", []) or [])
            if existing_tags:
                update_data["tags"] = sort_tags_by_priority(existing_tags)
            else:
                app_name = str(getattr(app, "name", "") or "")
                app_description = str(getattr(app, "description", "") or "")
                tags = TagAssignmentService.match_tags_by_keywords(app_name, app_description)
                update_data["tags"] = tags if tags else ["other"]

        # 如果是首次发布，设置发布时间
        if not app.published_at:
            update_data["published_at"] = datetime.now(UTC).replace(tzinfo=None)

        self.update(app, **update_data)

        # 4.先删除原有的知识库关联记录
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        # 5.新增新的知识库关联记录
        for dataset in draft_app_config["datasets"]:
            self.create(AppDatasetJoin, app_id=app_id, dataset_id=dataset["id"])

        # 6.获取应用草稿记录，并移除id、version、config_type、updated_at、created_at字段
        draft_app_config_copy = app.draft_app_config.__dict__.copy()
        remove_fields(
            draft_app_config_copy,
            ["id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"]
        )

        # 7.获取当前最大的发布版本
        max_version = self.db.session.query(func.coalesce(func.max(AppConfigVersion.version), 0)).filter(
            AppConfigVersion.app_id == app_id,
            AppConfigVersion.config_type == AppConfigType.PUBLISHED.value,
        ).scalar()

        # 8.新增发布历史配置
        self.create(
            AppConfigVersion,
            version=max_version + 1,
            config_type=AppConfigType.PUBLISHED.value,
            **draft_app_config_copy,
        )

        self._enqueue_mcp_tool_snapshot_prewarm(app.id, AppConfigType.PUBLISHED.value)

        if self.public_agent_registry_service:
            self._enqueue_public_app_registry_sync(app.id)
        logging.info(f"应用已发布: app_id={app_id}, share_to_square={share_to_square}")
        return app

    def cancel_publish_app_config(self, app_id: UUID, account: Account) -> App:
        """根据传递的应用id+账号，取消发布指定的应用配置，并从应用广场移除"""
        # 1.获取应用信息并校验权限
        app = self.get_app(app_id, account)

        # 2.检测下当前应用的状态是否为已发布
        if app.status != AppStatus.PUBLISHED.value:
            raise FailException("当前应用未发布，请核实后重试")

        # 3.修改账号的发布状态，清空关联配置id，并从应用广场移除
        self.update(
            app,
            status=AppStatus.DRAFT.value,
            app_config_id=None,
            is_public=False,  # 从应用广场移除
            published_at=None,  # 清空发布时间
        )

        if self.public_agent_registry_service:
            self._sync_public_app_registry_after_unpublish(app.id)
        logging.info(f"应用已取消发布并从应用广场移除: app_id={app_id}")
        return app

    def get_publish_histories_with_page(
            self,
            app_id: UUID,
            req: GetPublishHistoriesWithPageReq,
            account: Account
    ) -> tuple[list[AppConfigVersion], Paginator]:
        """根据传递的应用id+请求数据，获取指定应用的发布历史配置列表信息"""
        # 1.获取应用信息并校验权限
        self.get_app(app_id, account)

        # 2.构建分页器
        paginator = Paginator(db=self.db, req=req)

        # 3.执行分页并获取数据
        app_config_versions = paginator.paginate(
            self.db.session.query(AppConfigVersion).filter(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED.value,
            ).order_by(desc("version"))
        )

        return app_config_versions, paginator

    def get_versions(self, app_id: UUID, account: Account) -> list[AppConfigVersion]:
        """获取指定应用的版本对比数据，包含当前草稿和全部发布历史。"""
        app = self.get_app(app_id, account)
        display_config_loader = getattr(self.app_config_service, "get_version_display_config", None)

        draft_version = app.draft_app_config
        draft_version.is_current_published = False
        if callable(display_config_loader):
            draft_version.display_config = display_config_loader(
                draft_version,
                current_account_id=account.id,
                current_app_id=app_id,
            )

        published_versions = (
            self.db.session.query(AppConfigVersion)
            .filter(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED.value,
            )
            .order_by(desc("version"))
            .all()
        )

        current_published_version = None
        if app.status == AppStatus.PUBLISHED.value and published_versions:
            current_published_version = published_versions[0].version

        for published_version in published_versions:
            published_version.is_current_published = (
                current_published_version is not None
                and published_version.version == current_published_version
            )
            if callable(display_config_loader):
                published_version.display_config = display_config_loader(
                    published_version,
                    current_account_id=account.id,
                    current_app_id=app_id,
                )

        return [draft_version, *published_versions]

    def fallback_history_to_draft(
            self,
            app_id: UUID,
            app_config_version_id: UUID,
            account: Account,
    ) -> AppConfigVersion:
        """根据传递的应用id、历史配置版本id、账号信息，回退特定配置到草稿"""
        # 1.校验应用权限并获取信息
        app = self.get_app(app_id, account)

        # 2.查询指定的历史版本配置id
        app_config_version = self.get(AppConfigVersion, app_config_version_id)
        if not app_config_version:
            raise NotFoundException("该历史版本配置不存在，请核实后重试")

        # 3.校验历史版本配置信息（剔除已删除的工具、知识库、工作流）
        draft_app_config_dict = app_config_version.__dict__.copy()
        remove_fields(
            draft_app_config_dict,
            ["id", "app_id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"]
        )

        # 4.校验历史版本配置信息
        draft_app_config_dict = self._validate_draft_app_config(draft_app_config_dict, account, app_id)

        # 5.更新草稿配置信息
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # todo:更新时间补丁信息
            updated_at=datetime.now(UTC),
            **draft_app_config_dict,
        )

        prepared_mcp_tool_snapshots = self.app_config_service.prepare_mcp_tool_snapshots(
            getattr(draft_app_config_record, "mcp_bindings", []),
            getattr(draft_app_config_record, "mcp_tool_snapshots", []),
        )
        if getattr(draft_app_config_record, "mcp_tool_snapshots", []) != prepared_mcp_tool_snapshots:
            self.update(
                draft_app_config_record,
                updated_at=datetime.now(UTC),
                mcp_tool_snapshots=prepared_mcp_tool_snapshots,
            )

        self._enqueue_mcp_tool_snapshot_prewarm(app.id, AppConfigType.DRAFT.value)

        return draft_app_config_record

    def get_debug_conversation_summary(self, app_id: UUID, account: Account) -> str:
        """根据传递的应用id+账号获取指定应用的调试会话长期记忆"""
        # 1.获取应用信息并校验权限
        app = self.get_app(app_id, account)

        # 2.获取应用的草稿配置，并校验长期记忆是否启用
        draft_app_config = self.get_draft_app_config(app_id, account, persist_changes=False)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("该应用并未开启长期记忆，无法获取")

        return app.debug_conversation.summary

    def update_debug_conversation_summary(self, app_id: UUID, summary: str, account: Account) -> Conversation:
        """根据传递的应用id+总结更新指定应用的调试长期记忆"""
        # 1.获取应用信息并校验权限
        app = self.get_app(app_id, account)

        # 2.获取应用的草稿配置，并校验长期记忆是否启用
        draft_app_config = self.get_draft_app_config(app_id, account, persist_changes=False)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("该应用并未开启长期记忆，无法获取")

        # 3.更新应用长期记忆
        debug_conversation = app.debug_conversation
        self.update(debug_conversation, summary=summary)

        return debug_conversation

    def delete_debug_conversation(self, app_id: UUID, account: Account) -> App:
        """根据传递的应用id，删除指定的应用调试会话"""
        # 1.获取应用信息并校验权限
        app = self.get_app(app_id, account)

        # 2.判断是否存在debug_conversation_id这个数据，如果不存在表示没有会话，无需执行任何操作
        if not app.debug_conversation_id:
            return app

        # 3.否则将debug_conversation_id的值重置为None
        self.update(app, debug_conversation_id=None)

        return app

    def _resolve_debug_conversation(
        self,
        app: App,
        account: Account,
        conversation_id: UUID | None = None,
        sync_active: bool = False,
    ) -> Conversation:
        """解析并返回应用调试会话，必要时同步应用当前调试会话指针"""
        if conversation_id is None:
            return app.debug_conversation

        conversation = self.get(Conversation, conversation_id)
        if (
            not conversation
            or conversation.app_id != app.id
            or conversation.created_by != account.id
            or conversation.is_deleted
            or conversation.invoke_from != InvokeFrom.DEBUGGER.value
        ):
            raise NotFoundException("该应用调试会话不存在或已被删除，请核实后重试")

        if sync_active and app.debug_conversation_id != conversation.id:
            self.update(app, debug_conversation_id=conversation.id)

        return conversation

    def _build_runtime_tools(
        self,
        app_id: UUID,
        account: Account,
        draft_app_config: dict[str, Any],
        flask_app: Flask | None = None,
        runtime_context: dict[str, Any] | None = None,
    ) -> list[Any]:
        """根据应用草稿配置构建运行时工具列表"""
        return self._build_runtime_tools_for_config(
            app_config_service=self.app_config_service,
            retrieval_service=self.retrieval_service,
            skill_service=self._get_skill_service(),
            app_service=self,
            account=account,
            app_id=app_id,
            draft_app_config=draft_app_config,
            flask_app=flask_app,
            runtime_context=runtime_context,
        )

    @staticmethod
    def _build_skill_prompt_appendix(skill_bindings: list[dict[str, Any]] | None) -> str:
        """把已绑定 Skill 的正文拼成一段额外提示词。"""
        if not isinstance(skill_bindings, list) or not skill_bindings:
            return ""

        sections: list[str] = []
        for binding in skill_bindings:
            if not isinstance(binding, dict):
                continue

            title = str(binding.get("label") or binding.get("name") or binding.get("source_key") or "Skill").strip()
            readme = str(binding.get("readme") or binding.get("description") or "").strip()
            if not readme:
                continue

            sections.append(f"### {title}\n{readme}")

        if not sections:
            return ""

        return "## 已绑定 Skills\n\n" + "\n\n---\n\n".join(sections)

    @staticmethod
    def _build_mcp_prompt_appendix(mcp_bindings: list[dict[str, Any]] | None) -> str:
        """把已绑定 MCP 的基础信息拼成一段额外提示词。"""
        if not isinstance(mcp_bindings, list) or not mcp_bindings:
            return ""

        sections: list[str] = []
        for binding in mcp_bindings:
            if not isinstance(binding, dict) or not binding.get("enabled", True):
                continue

            title = str(binding.get("label") or binding.get("name") or binding.get("source_key") or "MCP").strip()
            description = str(binding.get("description") or "").strip()
            if not description:
                continue

            bullet = f"- {title}：{description}"
            source_key = str(binding.get("source_key") or "").strip()
            if source_key:
                bullet += f"（来源：{source_key}）"
            sections.append(bullet)

        if not sections:
            return ""

        appendix = [
            "## 已绑定 MCP",
            "",
            "如果用户的问题明显需要实时数据、外部服务或某个已绑定 MCP 的专长，请优先调用对应 MCP，不要用无关工具代替，也不要仅凭常识编造实时结果。",
            "",
            *sections,
        ]
        return "\n".join(appendix)

    @staticmethod
    def _build_mcp_snapshot_prompt_appendix(mcp_tool_snapshots: list[dict[str, Any]] | None) -> str:
        """把 MCP 快照状态拼成一段额外提示词。"""
        if not isinstance(mcp_tool_snapshots, list) or not mcp_tool_snapshots:
            return ""

        sections: list[str] = []
        for snapshot in mcp_tool_snapshots:
            if not isinstance(snapshot, dict):
                continue

            binding = snapshot.get("binding") if isinstance(snapshot.get("binding"), dict) else {}
            title = str(
                binding.get("label")
                or binding.get("name")
                or binding.get("source_key")
                or snapshot.get("binding_identity")
                or "MCP"
            ).strip()
            status = str(snapshot.get("status") or "").strip().lower() or "unknown"
            tool_count = int(snapshot.get("tool_count") or len(snapshot.get("tool_definitions") or []) or 0)
            last_error = str(snapshot.get("last_error") or "").strip()
            retryable = bool(snapshot.get("retryable", False))
            bullet = f"- {title}：状态 {status}"
            if tool_count:
                bullet += f"，工具数 {tool_count}"
            if retryable:
                bullet += "，可重试"
            if last_error and status in {"failed", "stale"}:
                bullet += f"，最近错误：{last_error}"
            sections.append(bullet)

        if not sections:
            return ""

        appendix = [
            "## MCP 快照状态",
            "",
            "只有状态为 ready 或 stale 且对应工具已进入运行时列表时，才优先按完整工具名调用；warming、failed、unsupported、empty 状态下不要假设该 MCP 可直接可用。",
            "",
            *sections,
        ]
        return "\n".join(appendix)

    @staticmethod
    def _build_runtime_mcp_tools_prompt_appendix(tools: list[Any] | None) -> str:
        """把运行时已经展开出来的 MCP 工具名拼成一段额外提示词。"""
        if not isinstance(tools, list) or not tools:
            return ""

        sections: list[str] = []
        for tool in tools:
            tool_name = str(getattr(tool, "name", "") or "").strip()
            if not tool_name.startswith("mcp__"):
                continue
            tool_description = str(getattr(tool, "description", "") or "").strip()
            if not tool_description:
                continue
            sections.append(f"- {tool_name}：{tool_description}")

        if not sections:
            return ""

        appendix = [
            "## 运行时可用的 MCP 工具",
            "",
            "调用 MCP 时请使用下面列出的**完整工具名**，不要自己猜工具名或缩写。",
            "",
            *sections,
        ]
        return "\n".join(appendix)

    @staticmethod
    def _build_runtime_tools_for_config(
        *,
        app_config_service: AppConfigService,
        retrieval_service: RetrievalService,
        skill_service: SkillService | None = None,
        app_service: Any | None = None,
        account: Account,
        app_id: UUID | None = None,
        draft_app_config: dict[str, Any],
        flask_app: Flask | None = None,
        runtime_context: dict[str, Any] | None = None,
    ) -> list[Any]:
        """根据应用配置构建运行时工具列表，供多入口复用。"""
        tools = app_config_service.get_langchain_tools_by_tools_config(draft_app_config.get("tools", []))
        get_mcp_tools = getattr(app_config_service, "get_langchain_tools_by_mcp_bindings", None)
        if callable(get_mcp_tools):
            tools.extend(
                get_mcp_tools(
                    draft_app_config.get("mcp_bindings", []),
                    draft_app_config.get("mcp_tool_snapshots", []),
                )
            )

        if skill_service is not None and app_id is not None:
            tools.extend(
                skill_service.get_langchain_tools_by_skill_bindings(
                    draft_app_config.get("skills", []),
                    runtime_context={
                        "app_id": str(app_id),
                        "account_id": str(account.id),
                    },
                )
            )

        if draft_app_config.get("datasets"):
            runtime_flask_app = flask_app
            if runtime_flask_app is None and has_app_context():
                runtime_flask_app = current_app._get_current_object()
            if runtime_flask_app is None:
                raise FailException("构建知识库检索工具失败: 缺少 Flask application context")
            dataset_retrieval = retrieval_service.create_langchain_tool_from_search(
                flask_app=runtime_flask_app,
                dataset_ids=[dataset["id"] for dataset in draft_app_config.get("datasets", [])],
                account_id=account.id,
                retrieval_source=RetrievalSource.APP.value,
                **draft_app_config.get("retrieval_config", {}),
            )
            tools.append(dataset_retrieval)

        if draft_app_config.get("workflows"):
            workflow_tools = app_config_service.get_langchain_tools_by_workflow_ids(
                [workflow["id"] for workflow in draft_app_config.get("workflows", [])]
            )
            tools.extend(workflow_tools)

        if app_service is not None and app_id is not None:
            get_agent_binding_tools = getattr(app_service, "get_langchain_tools_by_agent_bindings", None)
            if callable(get_agent_binding_tools):
                tools.extend(
                    get_agent_binding_tools(
                        draft_app_config.get("agent_bindings", []),
                        account=account,
                        app_id=app_id,
                        flask_app=flask_app,
                        runtime_context=runtime_context,
                    )
                )

        return tools

    @staticmethod
    def _build_agent_binding_prompt_appendix(agent_bindings: list[dict[str, Any]] | None) -> str:
        """把已绑定 Agent 的名称、描述和调用模式拼成一段额外提示词。"""
        if not isinstance(agent_bindings, list) or not agent_bindings:
            return ""

        sections: list[str] = []
        for binding in agent_bindings:
            if not isinstance(binding, dict):
                continue

            title = str(binding.get("name") or binding.get("description") or binding.get("app_id") or "Agent").strip()
            description = str(binding.get("description") or "").strip()
            runtime_tool_name = str(binding.get("tool_name") or "").strip()
            invoke_mode = str(binding.get("invoke_mode") or "tool").strip().lower() or "tool"
            source_scope = str(binding.get("source_scope") or "").strip()

            bullet = f"- {title}"
            if description:
                bullet += f"：{description}"
            if source_scope:
                bullet += f"（{source_scope}）"
            bullet += "；"
            bullet += "通过 A2A 协议委派" if invoke_mode == "a2a" else "通过内部工具包装委派"
            if runtime_tool_name:
                bullet += f"；工具名：{runtime_tool_name}"
            sections.append(bullet)

        if not sections:
            return ""

        return (
            "## 已绑定 Agent 子应用\n\n"
            "如果用户的问题明显适合交给子应用处理，请优先调用对应工具，不要自己凭空编造结果。\n\n"
            + "\n".join(sections)
        )

    @staticmethod
    def _push_runtime_context(runtime_context: dict[str, Any] | None, next_app_id: UUID | str) -> dict[str, Any]:
        """把下一跳 app_id 压入运行时上下文调用栈。"""
        context = dict(runtime_context or {})
        normalized_next_app_id = str(next_app_id).strip()
        call_stack = [
            str(app_id).strip()
            for app_id in (context.get("call_stack") or [])
            if str(app_id).strip()
        ]
        if not call_stack:
            root_app_id = str(context.get("root_app_id") or normalized_next_app_id).strip() or normalized_next_app_id
            call_stack = [root_app_id]
            context["root_app_id"] = root_app_id

        if normalized_next_app_id and (not call_stack or call_stack[-1] != normalized_next_app_id):
            call_stack.append(normalized_next_app_id)

        context["call_stack"] = call_stack
        context["root_app_id"] = str(context.get("root_app_id") or call_stack[0]).strip() or call_stack[0]
        return context

    @staticmethod
    def _extract_a2a_answer_text(response: dict[str, Any]) -> str:
        """从公共 A2A 响应中提取可返回给工具的纯文本答案。"""
        if not isinstance(response, dict):
            return ""

        message = response.get("message", {})
        if isinstance(message, dict):
            parts = message.get("parts", [])
            if isinstance(parts, list):
                text_parts: list[str] = []
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    if str(part.get("type", "")).strip() != "text":
                        continue
                    text = str(part.get("text", "")).strip()
                    if text:
                        text_parts.append(text)
                if text_parts:
                    return "\n".join(text_parts).strip()

        metadata = response.get("metadata", {})
        if isinstance(metadata, dict):
            error = str(metadata.get("error", "")).strip()
            if error:
                return error
            status = str(metadata.get("status", "")).strip()
            if status:
                return status

        return ""

    def get_langchain_tools_by_agent_bindings(
        self,
        agent_bindings: list[dict[str, Any]] | None,
        *,
        account: Account | None,
        app_id: UUID,
        flask_app: Flask | None = None,
        runtime_context: dict[str, Any] | None = None,
    ) -> list[BaseTool]:
        """根据 Agent 绑定列表生成 LangChain 工具。"""
        if not isinstance(agent_bindings, list) or not agent_bindings:
            return []

        tools: list[BaseTool] = []
        normalized_runtime_context = self._push_runtime_context(runtime_context, app_id)
        runtime_account_id_text = str(
            normalized_runtime_context.get("account_id")
            or getattr(account, "id", "")
            or ""
        ).strip()
        normalized_runtime_context["account_id"] = runtime_account_id_text
        runtime_account_id: UUID | str | None = None
        if runtime_account_id_text:
            try:
                runtime_account_id = UUID(runtime_account_id_text)
            except Exception:
                runtime_account_id = runtime_account_id_text
        runtime_account = SimpleNamespace(id=runtime_account_id)

        for binding in agent_bindings:
            if not isinstance(binding, dict):
                continue

            target_app_id = str(binding.get("app_id") or "").strip()
            if not target_app_id:
                continue

            tool_name = str(
                binding.get("tool_name") or self.app_config_service._build_agent_runtime_tool_name(target_app_id)
            ).strip()
            binding_title = str(binding.get("name") or binding.get("description") or target_app_id).strip()
            binding_description = str(binding.get("description") or "").strip()
            binding_invoke_mode = str(binding.get("invoke_mode") or "tool").strip().lower() or "tool"

            class AgentBindingQuery(BaseModel):
                """Agent 子应用输入结构。"""

                query: str = Field(description=f"需要委派给子应用 {binding_title} 处理的问题")

            def _invoke_agent_binding(query: str, *, _binding=binding, _tool_name=tool_name) -> str:
                """封装 Agent 子应用调用逻辑。"""
                try:
                    return self._invoke_agent_binding_target(
                        binding=_binding,
                        query=query,
                        account=runtime_account,
                        flask_app=flask_app,
                        runtime_context=normalized_runtime_context,
                    )
                except Exception as exc:
                    logging.exception("调用子 Agent 工具失败: tool_name=%s, error=%s", _tool_name, str(exc))
                    return f"调用子应用失败: {str(exc)}"

            delegate_tool = tool(tool_name, args_schema=AgentBindingQuery)(_invoke_agent_binding)
            delegate_tool.description = (
                f"委派给子应用 {binding_title} 执行。"
                f"{f' 描述: {binding_description}。' if binding_description else ''}"
                f" 调用模式: {'A2A' if binding_invoke_mode == 'a2a' else '内部工具'}。"
            ).strip()
            tools.append(delegate_tool)

        return tools

    def _invoke_agent_binding_target(
        self,
        *,
        binding: dict[str, Any],
        query: str,
        account: Account | SimpleNamespace | None,
        flask_app: Flask | None = None,
        runtime_context: dict[str, Any] | None = None,
    ) -> str:
        """实际执行一个 Agent 子应用绑定。"""
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return "用户问题为空，无法委派子应用"

        target_app_id = str(binding.get("app_id") or "").strip()
        if not target_app_id:
            return "子应用绑定缺少有效的 app_id"

        normalized_runtime_context = self._push_runtime_context(runtime_context, target_app_id)
        call_stack = [str(app_id).strip() for app_id in normalized_runtime_context.get("call_stack", []) if str(app_id).strip()]
        if len(call_stack) != len(set(call_stack)):
            return f"检测到 Agent 调用循环，已停止调用子应用 {target_app_id}"

        try:
            target_app_uuid = UUID(target_app_id)
        except Exception:
            return "子应用绑定的 app_id 格式错误"

        target_app = self.db.session.query(App).filter(
            App.id == target_app_uuid,
            App.status == AppStatus.PUBLISHED.value,
        ).one_or_none()
        if not target_app:
            return f"子应用 {target_app_id} 不存在或未发布，已自动跳过"

        caller_account_id = str(
            normalized_runtime_context.get("account_id")
            or getattr(account, "id", "")
            or ""
        ).strip()
        effective_invoke_mode = "a2a" if target_app.is_public else "tool"
        if effective_invoke_mode == "a2a":
            from .public_agent_a2a_service import PublicAgentA2AService

            public_agent_a2a_service = PublicAgentA2AService(
                db=self.db,
                app_service=self,
                app_config_service=self.app_config_service,
                language_model_service=self.language_model_service,
                public_agent_registry_service=self.public_agent_registry_service,
                conversation_service=self.conversation_service,
            )
            response = public_agent_a2a_service.send_message(
                target_app_id,
                {
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "text": normalized_query}],
                    },
                    "metadata": {
                        "runtime_context": normalized_runtime_context,
                        **({"caller_account_id": caller_account_id} if caller_account_id else {}),
                    },
                },
                flask_app=flask_app,
            )
            return self._extract_a2a_answer_text(response) or "子应用已处理完成，但未返回文本答案"

        target_app_config = call_config_loader(
            self.app_config_service.get_app_config,
            target_app,
            persist_changes=False,
        )
        if hasattr(self.language_model_service, "resolve_runtime_language_model"):
            model_resolution = self.language_model_service.resolve_runtime_language_model(
                target_app_config.get("model_config", {}),
                image_urls=[],
                entrypoint=LanguageModelService.ENTRYPOINT_DEBUGGER,
            )
            llm = model_resolution.llm
        else:
            llm = self.language_model_service.load_language_model(target_app_config.get("model_config", {}))

        tools = self._build_runtime_tools(
            target_app.id,
            account,
            target_app_config,
            flask_app=flask_app,
            runtime_context=normalized_runtime_context,
        )
        agent = self._create_runtime_agent(
            llm,
            account,
            target_app_config,
            tools,
            flask_app=flask_app,
            language_model_service=self.language_model_service,
            invoke_from=InvokeFrom.DEBUGGER.value,
        )
        agent_result = agent.invoke(
            {
                "messages": [llm.convert_to_human_message(normalized_query, [])],
                "history": [],
                "long_term_memory": "",
            }
        )
        return str(getattr(agent_result, "answer", "") or "").strip() or "子应用已处理完成，但未返回文本答案"

    @classmethod
    def _create_runtime_agent(
        cls,
        llm: Any,
        account: Account,
        draft_app_config: dict[str, Any],
        tools: list[Any],
        enable_deep_thinking: bool = False,
        flask_app: Flask | None = None,
        language_model_service: Any | None = None,
        invoke_from: InvokeFrom = InvokeFrom.DEBUGGER.value,
    ) -> FunctionCallAgent | ReACTAgent | DeepThinkingAgent:
        """根据运行时配置创建Agent实例

        enable_deep_thinking=True 时选择 DeepThinkingAgent，
        否则按模型能力选择 FunctionCallAgent 或 ReACTAgent。
        """
        if enable_deep_thinking:
            agent_class = DeepThinkingAgent
        else:
            agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL.value in llm.features else ReACTAgent

        skill_prompt_appendix = cls._build_skill_prompt_appendix(draft_app_config.get("skills", []))
        agent_binding_prompt_appendix = cls._build_agent_binding_prompt_appendix(
            draft_app_config.get("agent_bindings", [])
        )
        mcp_prompt_appendix = cls._build_mcp_prompt_appendix(draft_app_config.get("mcp_bindings", []))
        mcp_snapshot_prompt_appendix = cls._build_mcp_snapshot_prompt_appendix(
            draft_app_config.get("mcp_tool_snapshots", [])
        )
        runtime_mcp_tools_prompt_appendix = cls._build_runtime_mcp_tools_prompt_appendix(tools)
        preset_prompt = draft_app_config["preset_prompt"]
        prompt_parts = [preset_prompt.strip()]
        if skill_prompt_appendix:
            prompt_parts.append(skill_prompt_appendix.strip())
        if agent_binding_prompt_appendix:
            prompt_parts.append(agent_binding_prompt_appendix.strip())
        if mcp_prompt_appendix:
            prompt_parts.append(mcp_prompt_appendix.strip())
        if mcp_snapshot_prompt_appendix:
            prompt_parts.append(mcp_snapshot_prompt_appendix.strip())
        if runtime_mcp_tools_prompt_appendix:
            prompt_parts.append(runtime_mcp_tools_prompt_appendix.strip())
        preset_prompt = "\n\n".join(part for part in prompt_parts if part)

        return agent_class(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=invoke_from,
                preset_prompt=preset_prompt,
                enable_long_term_memory=draft_app_config["long_term_memory"]["enable"],
                enable_deep_thinking=enable_deep_thinking,
                runtime_flask_app=flask_app,
                language_model_service=language_model_service,
                tools=tools,
                review_config=draft_app_config["review_config"],
            ),
        )

    def _build_compare_history_prompt_messages(
        self,
        llm: Any,
        history_entries: list[dict[str, str]],
        message_limit: int,
        max_token_limit: int = 2000,
    ) -> list[Any]:
        """根据前端传递的历史问答构建对比调试上下文"""
        if message_limit <= 0 or not history_entries:
            return []

        prompt_messages = []
        for history_item in history_entries[-message_limit:]:
            query = str(history_item.get("query", "")).strip()
            answer = str(history_item.get("answer", "")).strip()
            if not query or not answer:
                continue
            prompt_messages.extend([
                llm.convert_to_human_message(query),
                AIMessage(content=answer),
            ])

        if not prompt_messages:
            return []

        try:
            return trim_messages(
                messages=prompt_messages,
                max_tokens=max_token_limit,
                token_counter=llm,
                strategy="last",
                start_on="human",
                end_on="ai",
            )
        except NotImplementedError:
            token_buffer_memory = TokenBufferMemory(
                db=self.db,
                conversation=None,
                model_instance=llm,
            )
            return trim_messages(
                messages=prompt_messages,
                max_tokens=max_token_limit,
                token_counter=token_buffer_memory._fallback_token_counter,
                strategy="last",
                start_on="human",
                end_on="ai",
            )

    def _get_debug_long_term_memory_snapshot(self, app: App, account: Account) -> str:
        """获取当前应用已有调试会话的长期记忆快照，不主动创建新会话"""
        if not app.debug_conversation_id:
            return ""

        debug_conversation = self.db.session.query(Conversation).filter(
            Conversation.id == app.debug_conversation_id,
            Conversation.app_id == app.id,
            Conversation.created_by == account.id,
            Conversation.invoke_from == InvokeFrom.DEBUGGER.value,
            Conversation.is_deleted == False,
        ).one_or_none()

        return debug_conversation.summary if debug_conversation else ""

    @staticmethod
    def _normalize_paginated_ids(paginated_items: list[Any]) -> list[Any]:
        """提取分页结果中的主键值，兼容 SQLAlchemy Row/tuple 标量结果。"""
        normalized_ids = []
        for item in paginated_items:
            if isinstance(item, UUID):
                normalized_ids.append(item)
                continue

            mapping = getattr(item, "_mapping", None)
            if mapping:
                normalized_ids.append(next(iter(mapping.values()), None))
                continue

            if isinstance(item, (tuple, list)):
                normalized_ids.append(item[0] if item else None)
                continue

            normalized_ids.append(item)

        return [item for item in normalized_ids if item is not None]

    def _stream_agent_events(
        self,
        app_id: UUID,
        account: Account,
        draft_app_config: dict[str, Any],
        llm: Any,
        query: str,
        image_urls: list[str],
        history: list[Any],
        long_term_memory: str,
        conversation_id: str = "",
        message_id: str = "",
        agent_thoughts: dict[str, Any] | None = None,
        enable_deep_thinking: bool = False,
        flask_app: Flask | None = None,
    ) -> Generator[str, None, None]:
        """统一流式执行应用Agent并输出事件"""
        tools = self._build_runtime_tools(app_id, account, draft_app_config, flask_app=flask_app)
        agent = self._create_runtime_agent(
            llm,
            account,
            draft_app_config,
            tools,
            enable_deep_thinking,
            flask_app=flask_app,
            language_model_service=self.language_model_service,
        )
        agent_thoughts = agent_thoughts if agent_thoughts is not None else {}

        for agent_thought in agent.stream({
            "messages": [llm.convert_to_human_message(query, image_urls)],
            "history": history,
            "long_term_memory": long_term_memory,
        }):
            event_id = str(agent_thought.id)

            if agent_thought.event != QueueEvent.PING.value:
                if agent_thought.event == QueueEvent.AGENT_MESSAGE.value:
                    if event_id not in agent_thoughts:
                        agent_thoughts[event_id] = agent_thought
                    else:
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            "message": agent_thought.message,
                            "message_token_count": agent_thought.message_token_count,
                            "message_unit_price": agent_thought.message_unit_price,
                            "message_price_unit": agent_thought.message_price_unit,
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "answer_token_count": agent_thought.answer_token_count,
                            "answer_unit_price": agent_thought.answer_unit_price,
                            "answer_price_unit": agent_thought.answer_price_unit,
                            "total_token_count": agent_thought.total_token_count,
                            "total_price": agent_thought.total_price,
                            "latency": agent_thought.latency,
                        })
                else:
                    agent_thoughts[event_id] = agent_thought

            usage_summary = summarize_agent_thoughts(agent_thoughts.values())
            data = {
                **agent_thought.model_dump(include={
                    "event", "thought", "observation", "tool", "tool_input", "answer",
                    "total_token_count", "total_price", "latency",
                }),
                "aggregate_total_token_count": usage_summary.total_token_count,
                "aggregate_total_price": usage_summary.total_price,
                "aggregate_latency": usage_summary.latency,
                "id": event_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event.value}\ndata:{json.dumps(data)}\n\n"


    def debug_chat(self, app_id: UUID, req: DebugChatReq, account: Account) -> Generator:
        """根据传递的应用id+提问query向特定的应用发起会话调试"""
        # 1.获取应用信息并校验权限
        app = self.get_app(app_id, account)

        # 2.获取应用的最新草稿配置信息
        draft_app_config = self.get_draft_app_config(app_id, account, persist_changes=False)

        # 3.获取当前应用的调试会话信息（支持按conversation_id切换）
        debug_conversation_id = UUID(req.conversation_id.data) if req.conversation_id.data else None
        debug_conversation = self._resolve_debug_conversation(
            app=app,
            account=account,
            conversation_id=debug_conversation_id,
            sync_active=True,
        )

        # 4.在落库前解析运行时模型能力，避免带图请求被静默降级
        if hasattr(self.language_model_service, "resolve_runtime_language_model"):
            model_resolution = self.language_model_service.resolve_runtime_language_model(
                draft_app_config.get("model_config", {}),
                image_urls=req.image_urls.data,
                entrypoint=LanguageModelService.ENTRYPOINT_DEBUGGER,
            )
            llm = model_resolution.llm
            draft_app_config["capabilities"] = model_resolution.capabilities
        else:
            model_resolution = None
            llm = self.language_model_service.load_language_model(draft_app_config.get("model_config", {}))

        # 5.新建一条消息记录
        message = self.create(
            Message,
            app_id=app_id,
            conversation_id=debug_conversation.id,
            invoke_from=InvokeFrom.DEBUGGER.value,
            created_by=account.id,
            query=req.query.data,
            image_urls=req.image_urls.data,
            status=MessageStatus.NORMAL.value,
        )

        # 6.实例化TokenBufferMemory用于提取短期记忆
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=debug_conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=draft_app_config["dialog_round"],
        )

        agent_thoughts = {}
        runtime_flask_app = current_app._get_current_object() if has_app_context() else None
        yield from self._stream_agent_events(
            app_id=app_id,
            account=account,
            draft_app_config=draft_app_config,
            llm=llm,
            query=req.query.data,
            image_urls=req.image_urls.data,
            history=history,
            long_term_memory=debug_conversation.summary,
            conversation_id=str(debug_conversation.id),
            message_id=str(message.id),
            agent_thoughts=agent_thoughts,
            enable_deep_thinking=bool(req.enable_deep_thinking.data),
            flask_app=runtime_flask_app,
        )

        # 17.将消息以及推理过程添加到数据库
        self.conversation_service.save_agent_thoughts(
            account_id=account.id,
            app_id=app_id,
            app_config=draft_app_config,
            conversation_id=debug_conversation.id,
            message_id=message.id,
            agent_thoughts=[agent_thought for agent_thought in agent_thoughts.values()],
        )

    def prompt_compare_chat(self, app_id: UUID, req: Any, account: Account) -> Generator[str, None, None]:
        """根据传递的应用id发起无状态提示词对比调试"""
        app = self.get_app(app_id, account)
        draft_app_config = self.get_draft_app_config(app_id, account, persist_changes=False)
        overrides = self._validate_draft_app_config(
            {
                "preset_prompt": req.preset_prompt.data,
                "model_config": req.model_config.data,
            },
            account,
        )
        draft_app_config.update(overrides)

        llm = self.language_model_service.load_language_model(draft_app_config.get("model_config", {}))
        history = self._build_compare_history_prompt_messages(
            llm=llm,
            history_entries=req.history.data,
            message_limit=draft_app_config["dialog_round"],
        )
        long_term_memory = ""
        if draft_app_config["long_term_memory"]["enable"]:
            long_term_memory = self._get_debug_long_term_memory_snapshot(app, account)

        yield from self._stream_agent_events(
            app_id=app_id,
            account=account,
            draft_app_config=draft_app_config,
            llm=llm,
            query=req.query.data,
            image_urls=[],
            history=history,
            long_term_memory=long_term_memory,
            conversation_id=req.lane_id.data.strip() if req.lane_id.data else str(uuid4()),
            message_id=str(uuid4()),
            flask_app=current_app._get_current_object() if has_app_context() else None,
        )

    def stop_debug_chat(self, app_id: UUID, task_id: UUID, account: Account) -> None:
        """根据传递的应用id+任务id+账号，停止某个应用的调试会话，中断流式事件"""
        # 1.获取应用信息并校验权限
        self.get_app(app_id, account)

        # 2.调用智能体队列管理器停止特定任务
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.DEBUGGER.value, account.id)

    def stop_prompt_compare_chat(self, app_id: UUID, task_id: UUID, account: Account) -> None:
        """根据传递的应用id+任务id停止某个提示词对比调试会话"""
        self.get_app(app_id, account)
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.DEBUGGER.value, account.id)

    def get_debug_conversation_messages_with_page(
            self,
            app_id: UUID,
            req: GetDebugConversationMessagesWithPageReq,
            account: Account
    ) -> tuple[list[Message], Paginator]:
        """根据传递的应用id+请求数据，获取调试会话消息列表分页数据"""

        # 1. 获取应用信息并校验权限
        app = self.get_app(app_id, account)

        # 2. 获取应用的调试会话（支持按conversation_id切换）
        debug_conversation_id = UUID(req.conversation_id.data) if req.conversation_id.data else None
        debug_conversation = self._resolve_debug_conversation(
            app=app,
            account=account,
            conversation_id=debug_conversation_id,
            sync_active=False,
        )

        # 3. 构建分页器并构建过滤条件
        paginator = Paginator(db=self.db, req=req)
        filters = [
            Message.conversation_id == debug_conversation.id,
            Message.status.in_([MessageStatus.STOP.value, MessageStatus.NORMAL.value]),
            Message.answer != "",
            Message.is_deleted == False,
        ]

        if req.created_at.data:
            # 4. 将时间戳转换成 DateTime
            created_at_datetime = datetime.fromtimestamp(req.created_at.data, UTC)
            filters.append(Message.created_at <= created_at_datetime)

        # 5. 先分页查询 ID 列表
        paginated_ids = paginator.paginate(
            self.db.session.query(Message.id)
            .filter(*filters)
            .order_by(desc(Message.created_at), desc(Message.id))
        )

        normalized_ids = self._normalize_paginated_ids(paginated_ids)
        if not normalized_ids:
            return [], paginator

        # 6. 再根据 ID 查询完整消息及其关联内容
        messages = (
            self.db.session.query(Message)
            .options(selectinload(Message.agent_thoughts))
            .filter(Message.id.in_(normalized_ids))
            .order_by(desc(Message.created_at), desc(Message.id))
            .all()
        )

        return messages, paginator

    def get_published_config(self, app_id: UUID, account: Account) -> dict[str, Any]:
        """根据传递的应用id+账号 获取应用的发布配置"""
        # 1.获取应用信息并校验权限
        app = self.get_app(app_id, account)

        # 2.构建发布配置并返回
        return {
            "web_app": {
                "token": app.token_with_default,
                "status": app.status
            },
            "is_public": app.is_public,
            "category": getattr(app, "category", "general"),
        }

    def regenerate_web_app_token(self, app_id: UUID, account: Account) -> str:
        """根据传递的应用id+账号重新生成WebApp凭证标识"""
        # 1.获取应用信息并校验权限
        app = self.get_app(app_id, account)

        # 2.判断应用是否已发布
        if app.status != AppStatus.PUBLISHED.value:
            raise FailException("应用未发布 无法生成WebApp凭证标识")

        # 3.重新生成token并更新数据
        token = generate_random_string(16)
        self.update(app, token=token)

        return token

    def regenerate_icon(self, app_id: UUID, account: Account) -> str:
        """根据传递的应用id重新生成应用图标"""
        # 1.获取应用信息并校验权限
        app = self.get_app(app_id, account)

        # 2.使用图标生成服务生成新图标
        try:
            logging.info(f"重新生成应用图标: app_id={app_id}, name={app.name}")
            icon_url = self.icon_generator_service.generate_icon(
                name=app.name,
                description=app.description or ""
            )
            logging.info(f"重新生成图标成功: {icon_url}")
        except Exception as e:
            logging.error(f"重新生成图标失败: {str(e)}")
            # 直接抛出原始异常，保留错误信息
            raise

        # 3.更新应用图标
        self.update(app, icon=icon_url)

        return icon_url

    def generate_icon_preview(self, name: str, description: str) -> str:
        """生成图标预览（不保存到应用）"""
        try:
            logging.info(f"生成图标预览: name={name}")
            icon_url = self.icon_generator_service.generate_icon(
                name=name,
                description=description or ""
            )
            logging.info(f"生成图标预览成功: {icon_url}")
            return icon_url
        except Exception as e:
            logging.error(f"生成图标预览失败: {str(e)}")
            # 直接抛出原始异常，保留错误信息
            raise


    def _validate_draft_app_config(
        self,
        draft_app_config: dict[str, Any],
        account: Account,
        app_id: UUID | None = None,
    ) -> dict[str, Any]:
        """校验传递的应用草稿配置信息，返回校验后的数据"""
        # 1.校验上传的草稿配置中对应的字段，至少拥有一个可以更新的配置
        acceptable_fields = [
            "model_config", "dialog_round", "preset_prompt",
            "tools", "mcp_bindings", "mcp_tool_snapshots", "skills", "agent_bindings", "workflows", "datasets", "retrieval_config",
            "long_term_memory", "opening_statement", "opening_questions",
            "speech_to_text", "text_to_speech", "suggested_after_answer", "review_config",
        ]

        # 2.判断传递的草稿配置是否在可接受字段内
        if (
                not draft_app_config
                or not isinstance(draft_app_config, dict)
                or set(draft_app_config.keys()) - set(acceptable_fields)
        ):
            raise ValidateErrorException("草稿配置字段出错，请核实后重试")

        # 3.校验model_config字段，provider/model使用严格校验(出错时直接抛出) parameters使用宽松校验 出错时使用默认值
        if "model_config" in draft_app_config:
            # 3.1 获取模型配置并判断数据是否为字典
            model_config = draft_app_config["model_config"]
            if not isinstance(model_config, dict):
                raise ValidateErrorException("模型配置格式错误 请核实后重试")

            # 3.2 判断model_config键信息是否正确
            if set(model_config.keys()) != {"provider", "model", "parameters"}:
                raise ValidateErrorException("模型键配置格式错误 请核实后重试")

            if not isinstance(model_config["parameters"], dict):
                raise ValidateErrorException("模型参数配置格式错误 请核实后重试")

            # 3.3 判断模型提供者信息是否正确
            if not model_config["provider"] or not isinstance(model_config["provider"], str):
                raise ValidateErrorException("模型服务提供商类型必须为字符串")
            provider = self.language_model_manager.get_provider(model_config["provider"])
            if not provider:
                raise ValidateErrorException("该模型服务提供商不存在 请核实后重试")

            # 3.3 判断模型信息是否正确
            if not model_config["model"] or not isinstance(model_config["model"], str):
                raise ValidateErrorException("模型名字类型必须为字符串")
            model_entity = provider.get_model_entity(model_config["model"])
            if not model_entity:
                raise ValidateErrorException("该模型服务提供商下不存在该模型,请核实后重试")

            # 3.5 判断传递的parameters是否正确 如果不正确则设置为默认值 并剔除多余字段 补全未传递的字段
            parameters = {}
            for parameter in model_entity.parameters:
                # 3.6 从model_config中获取参数值，如果不存在则设置为默认值
                parameter_value = model_config["parameters"].get(parameter.name, parameter.default)

                # 3.7 判断参数是否必填
                if parameter.required:
                    # 3.8 参数必填，则值不允许为None，如果为None则设置默认值
                    if parameter_value is None:
                        parameter_value = parameter.default
                    else:
                        # 3.9 值非空则校验数据类型是否正确，不正确则设置默认值
                        if get_value_type(parameter_value) != parameter.type.value:
                            parameter_value = parameter.default
                else:
                    # 3.10 参数非必填，数据非空的情况下需要校验
                    if parameter_value is not None:
                        if get_value_type(parameter_value) != parameter.type.value:
                            parameter_value = parameter.default

                # 3.11 判断参数是否存在options，如果存在则数值必须在options中选择
                if parameter.options and parameter_value not in parameter.options:
                    parameter_value = parameter.default

                # 3.12 参数类型为int/float，如果存在min/max时候需要校验
                if parameter.type in [ModelParameterType.INT.value,
                                      ModelParameterType.FLOAT.value] and parameter_value is not None:
                    # 3.13 校验数值的min/max
                    if (
                            (parameter.min is not None and parameter_value < parameter.min)
                            or (parameter.max is not None and parameter_value > parameter.max)
                    ):
                        parameter_value = parameter.default

                parameters[parameter.name] = parameter_value

            # 3.13 覆盖Agent配置中的模型配置
            model_config["parameters"] = parameters
            draft_app_config["model_config"] = model_config

        # 4.校验dialog_round上下文轮数，校验数据类型以及范围
        if "dialog_round" in draft_app_config:
            dialog_round = draft_app_config["dialog_round"]
            if type(dialog_round) is not int or not (0 <= dialog_round <= 100):
                raise ValidateErrorException("携带上下文轮数范围为0-100")

        # 5.校验preset_prompt
        if "preset_prompt" in draft_app_config:
            preset_prompt = draft_app_config["preset_prompt"]
            if not isinstance(preset_prompt, str) or len(preset_prompt) > 5000:
                raise ValidateErrorException("人设与回复逻辑必须是字符串，长度在0-5000个字符")

        # 6.校验tools工具
        if "tools" in draft_app_config:
            tools = draft_app_config["tools"]
            validate_tools = []

            # 6.1 tools类型必须为列表，空列表则代表不绑定任何工具
            if not isinstance(tools, list):
                raise ValidateErrorException("工具列表必须是列表型数据")
            # 6.2 tools的长度不能超过5
            if len(tools) > 5:
                raise ValidateErrorException("Agent绑定的工具数不能超过5")
            # 6.3 循环校验工具里的每一个参数
            for tool in tools:
                # 6.4 校验tool非空并且类型为字典
                if not tool or not isinstance(tool, dict):
                    raise ValidateErrorException("绑定插件工具参数出错")
                # 6.5 校验工具的参数是不是type、provider_id、tool_id、params
                if set(tool.keys()) != {"type", "provider_id", "tool_id", "params"}:
                    raise ValidateErrorException("绑定插件工具参数出错")
                # 6.6 校验type类型是否为builtin_tool以及api_tool
                if tool["type"] not in ["builtin_tool", "api_tool"]:
                    raise ValidateErrorException("绑定插件工具参数出错")
                # 6.7 校验provider_id和tool_id
                if (
                        not tool["provider_id"]
                        or not tool["tool_id"]
                        or not isinstance(tool["provider_id"], str)
                        or not isinstance(tool["tool_id"], str)
                ):
                    raise ValidateErrorException("插件提供者或者插件标识参数出错")
                # 6.8 校验params参数，类型为字典
                if not isinstance(tool["params"], dict):
                    raise ValidateErrorException("插件自定义参数格式错误")
                # 6.9 校验对应的工具是否存在，而且需要划分成builtin_tool和api_tool
                if tool["type"] == "builtin_tool":
                    builtin_tool = self.builtin_provider_manager.get_tool(tool["provider_id"], tool["tool_id"])
                    if not builtin_tool:
                        continue
                else:
                    api_tool = self.db.session.query(ApiTool).filter(
                        ApiTool.provider_id == tool["provider_id"],
                        ApiTool.name == tool["tool_id"],
                        ApiTool.account_id == account.id,
                    ).one_or_none()
                    if not api_tool:
                        continue

                validate_tools.append(tool)

            # 6.10 校验绑定的工具是否重复
            check_tools = [f"{tool['provider_id']}_{tool['tool_id']}" for tool in validate_tools]
            if len(set(check_tools)) != len(validate_tools):
                raise ValidateErrorException("绑定插件存在重复")

            # 6.11 重新赋值工具
            draft_app_config["tools"] = validate_tools

        # 7.校验workflow 提取已发布+权限正确的工作流列表进行绑定(更新配置阶段不校验工作流是否可以正确运行)
        if "workflows" in draft_app_config:
            workflows = draft_app_config["workflows"]

            # 7.1 判断workflows是否为列表
            if not isinstance(workflows, list):
                raise ValidateErrorException("绑定工作流列表参数错误")

            # 7.2 判断关联的工作流列表是否超过五个
            if len(workflows) > 5:
                raise ValidateErrorException("Agent绑定的工作流数量不能超过5个")

            # 7.3 循环校验工作流的每个参数 类型必须是UUID
            for workflow in workflows:
                try:
                    UUID(workflow)
                except Exception as e:
                    raise ValidateErrorException("工作流参数必须是UUID")

            # 7.4 判断是否重复关联了工作流
            if len(set(workflows)) != len(workflows):
                raise ValidateErrorException("绑定工作流存在重复")

            # 7.5 校验关联工作流权限 剔除不属于当前账号 亦或者未发布的工作流
            workflow_records = self.db.session.query(Workflow).filter(
                Workflow.id.in_(workflows),
                Workflow.account_id == account.id,
                Workflow.status == WorkflowStatus.PUBLISHED.value
            ).all()

            workflow_sets = set([str(workflow_record.id) for workflow_record in workflow_records])
            draft_app_config["workflows"] = [workflow_id for workflow_id in workflows if workflow_id in workflow_sets]

        # 8.校验MCP绑定配置
        if "mcp_bindings" in draft_app_config:
            mcp_bindings = draft_app_config["mcp_bindings"]

            if not isinstance(mcp_bindings, list):
                raise ValidateErrorException("MCP绑定列表参数格式错误")
            if len(mcp_bindings) > 5:
                raise ValidateErrorException("Agent绑定的MCP数量不能超过5个")

            validate_mcp_bindings = []
            seen_binding_targets: set[str] = set()
            for binding in mcp_bindings:
                if not binding or not isinstance(binding, dict):
                    raise ValidateErrorException("MCP绑定参数出错")

                allowed_keys = {
                    "name", "description", "transport", "url", "enabled",
                    "headers", "tool_names", "timeout_seconds", "command",
                    "args", "env", "provider_key", "source_type",
                    "source_key", "source_url", "label", "icon", "category",
                }
                if set(binding.keys()) - allowed_keys:
                    raise ValidateErrorException("MCP绑定参数出错")

                name = str(binding.get("name", "")).strip()
                description = str(binding.get("description", "")).strip()
                transport = str(binding.get("transport", "streamable_http")).strip().lower() or "streamable_http"
                url = str(binding.get("url", "")).strip()
                command = str(binding.get("command", "")).strip()
                enabled = binding.get("enabled", True)
                headers = binding.get("headers", [])
                tool_names = binding.get("tool_names", [])
                timeout_seconds = binding.get("timeout_seconds", 30)
                args = binding.get("args", [])
                env = binding.get("env", {})
                provider_key = str(binding.get("provider_key", "")).strip()
                source_type = str(binding.get("source_type", "")).strip()
                source_key = str(binding.get("source_key", "")).strip()
                source_url = str(binding.get("source_url", "")).strip()
                label = str(binding.get("label", "")).strip()
                icon = str(binding.get("icon", "")).strip()
                category = str(binding.get("category", "")).strip()

                if not name or not isinstance(name, str):
                    raise ValidateErrorException("MCP绑定名称不能为空")
                if not isinstance(enabled, bool):
                    raise ValidateErrorException("MCP绑定启用状态格式错误")

                if transport in {"http", "sse", "streamable_http", "streamable-http"}:
                    if not url:
                        raise ValidateErrorException("MCP绑定URL不能为空")
                elif transport == "stdio":
                    if not command:
                        raise ValidateErrorException("MCP绑定命令不能为空")
                else:
                    raise ValidateErrorException("MCP transport格式错误")

                if not isinstance(headers, list):
                    raise ValidateErrorException("MCP headers格式错误")
                if not isinstance(tool_names, list):
                    raise ValidateErrorException("MCP tool_names格式错误")
                if not isinstance(args, list):
                    raise ValidateErrorException("MCP args格式错误")
                if not isinstance(env, dict):
                    raise ValidateErrorException("MCP env格式错误")
                if timeout_seconds is not None and (
                    not isinstance(timeout_seconds, int)
                    or isinstance(timeout_seconds, bool)
                    or timeout_seconds <= 0
                ):
                    raise ValidateErrorException("MCP timeout_seconds格式错误")

                normalized_headers = []
                for header in headers:
                    if not isinstance(header, dict):
                        raise ValidateErrorException("MCP headers格式错误")
                    if not str(header.get("key", "")).strip():
                        raise ValidateErrorException("MCP headers格式错误")
                    normalized_headers.append({
                        "key": str(header.get("key", "")).strip(),
                        "value": str(header.get("value", "")).strip(),
                    })

                normalized_tool_names = []
                for tool_name in tool_names:
                    normalized_tool_name = str(tool_name).strip()
                    if not normalized_tool_name:
                        continue
                    normalized_tool_names.append(normalized_tool_name)

                normalized_args = [str(arg).strip() for arg in args if str(arg).strip()]
                normalized_env = {
                    str(key).strip(): str(value).strip()
                    for key, value in env.items()
                    if str(key).strip()
                }

                binding_identity = provider_key or f"{transport}:{url or command}:{name}"
                if binding_identity in seen_binding_targets:
                    raise ValidateErrorException("MCP绑定存在重复")
                seen_binding_targets.add(binding_identity)

                validate_mcp_bindings.append({
                    "name": name,
                    "description": description,
                    "transport": transport,
                    "url": url,
                    "command": command,
                    "enabled": enabled,
                    "headers": normalized_headers,
                    "tool_names": normalized_tool_names,
                    "timeout_seconds": timeout_seconds or 30,
                    "args": normalized_args,
                    "env": normalized_env,
                    "provider_key": provider_key,
                    "source_type": source_type,
                    "source_key": source_key,
                    "source_url": source_url,
                    "label": label,
                    "icon": icon,
                    "category": category,
                })

            draft_app_config["mcp_bindings"] = validate_mcp_bindings

        # 9.校验skills技能列表
        if "skills" in draft_app_config:
            skills = draft_app_config["skills"]

            if not isinstance(skills, list):
                raise ValidateErrorException("绑定技能列表参数格式错误")

            skill_service = self._get_skill_service()
            _, validate_skills = skill_service.process_and_validate_skill_bindings(skills)
            draft_app_config["skills"] = validate_skills

        # 10.校验datasets知识库列表
        if "datasets" in draft_app_config:
            datasets = draft_app_config["datasets"]

            # 8.1 判断datasets类型是否为列表
            if not isinstance(datasets, list):
                raise ValidateErrorException("绑定知识库列表参数格式错误")
            # 8.2 判断关联的知识库列表是否超过5个
            if len(datasets) > 5:
                raise ValidateErrorException("Agent绑定的知识库数量不能超过5个")
            # 8.3 循环校验知识库的每个参数
            for dataset_id in datasets:
                try:
                    UUID(dataset_id)
                except Exception as e:
                    raise ValidateErrorException("知识库列表参数必须是UUID")
            # 8.4 判断是否传递了重复的知识库
            if len(set(datasets)) != len(datasets):
                raise ValidateErrorException("绑定知识库存在重复")
            # 8.5 校验绑定的知识库权限，剔除不属于当前账号的知识库
            dataset_records = self.db.session.query(Dataset).filter(
                Dataset.id.in_(datasets),
                Dataset.account_id == account.id,
            ).all()
            dataset_sets = set([str(dataset_record.id) for dataset_record in dataset_records])
            draft_app_config["datasets"] = [dataset_id for dataset_id in datasets if dataset_id in dataset_sets]

        # 11.校验retrieval_config检索配置
        if "retrieval_config" in draft_app_config:
            retrieval_config = draft_app_config["retrieval_config"]

            # 9.1 判断检索配置非空且类型为字典
            if not retrieval_config or not isinstance(retrieval_config, dict):
                raise ValidateErrorException("检索配置格式错误")
            # 9.2 校验检索配置的字段类型
            if set(retrieval_config.keys()) != {"retrieval_strategy", "k", "score"}:
                raise ValidateErrorException("检索配置格式错误")
            # 9.3 校验检索策略是否正确
            if retrieval_config["retrieval_strategy"] not in ["semantic", "full_text", "hybrid"]:
                raise ValidateErrorException("检测策略格式错误")
            # 9.4 校验最大召回数量
            if not isinstance(retrieval_config["k"], int) or not (0 <= retrieval_config["k"] <= 10):
                raise ValidateErrorException("最大召回数量范围为0-10")
            # 9.5 校验得分/最小匹配度
            score = retrieval_config["score"]
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not (0 <= score <= 1):
                raise ValidateErrorException("最小匹配范围为0-1")
            retrieval_config["score"] = float(score)

        # 12.校验long_term_memory长期记忆配置
        if "long_term_memory" in draft_app_config:
            long_term_memory = draft_app_config["long_term_memory"]

            # 10.1 校验长期记忆格式
            if not long_term_memory or not isinstance(long_term_memory, dict):
                raise ValidateErrorException("长期记忆设置格式错误")
            # 10.2 校验长期记忆属性
            if (
                    set(long_term_memory.keys()) != {"enable"}
                    or not isinstance(long_term_memory["enable"], bool)
            ):
                raise ValidateErrorException("长期记忆设置格式错误")

        # 13.校验opening_statement对话开场白
        if "opening_statement" in draft_app_config:
            opening_statement = draft_app_config["opening_statement"]

            # 11.1 校验对话开场白类型以及长度
            if not isinstance(opening_statement, str) or len(opening_statement) > 2000:
                raise ValidateErrorException("对话开场白的长度范围是0-2000")

        # 14.校验opening_questions开场建议问题列表
        if "opening_questions" in draft_app_config:
            opening_questions = draft_app_config["opening_questions"]

            # 12.1 校验是否为列表，并且长度不超过3
            if not isinstance(opening_questions, list) or len(opening_questions) > 3:
                raise ValidateErrorException("开场建议问题不能超过3个")
            # 12.2 开场建议问题每个元素都是一个字符串
            for opening_question in opening_questions:
                if not isinstance(opening_question, str):
                    raise ValidateErrorException("开场建议问题必须是字符串")

        # 15.校验speech_to_text语音转文本
        if "speech_to_text" in draft_app_config:
            speech_to_text = draft_app_config["speech_to_text"]

            # 13.1 校验语音转文本格式
            if not speech_to_text or not isinstance(speech_to_text, dict):
                raise ValidateErrorException("语音转文本设置格式错误")
            # 13.2 校验语音转文本属性
            if (
                    set(speech_to_text.keys()) != {"enable"}
                    or not isinstance(speech_to_text["enable"], bool)
            ):
                raise ValidateErrorException("语音转文本设置格式错误")

        # 16.校验text_to_speech文本转语音设置
        if "text_to_speech" in draft_app_config:
            text_to_speech = draft_app_config["text_to_speech"]

            # 14.1 校验字典格式
            if not isinstance(text_to_speech, dict):
                raise ValidateErrorException("文本转语音设置格式错误")
            # 14.2 校验字段类型
            if (
                    set(text_to_speech.keys()) != {"enable", "voice", "auto_play"}
                    or not isinstance(text_to_speech["enable"], bool)
                    or text_to_speech["voice"] not in ALLOWED_AUDIO_VOICES
                    or not isinstance(text_to_speech["auto_play"], bool)
            ):
                raise ValidateErrorException("文本转语音设置格式错误")

        # 17.校验回答后生成建议问题
        if "suggested_after_answer" in draft_app_config:
            suggested_after_answer = draft_app_config["suggested_after_answer"]

            # 10.1 校验回答后建议问题格式
            if not suggested_after_answer or not isinstance(suggested_after_answer, dict):
                raise ValidateErrorException("回答后建议问题设置格式错误")
            # 10.2 校验回答后建议问题格式
            if (
                    set(suggested_after_answer.keys()) != {"enable"}
                    or not isinstance(suggested_after_answer["enable"], bool)
            ):
                raise ValidateErrorException("回答后建议问题设置格式错误")

        # 17.校验review_config审核配置
        if "review_config" in draft_app_config:
            review_config = draft_app_config["review_config"]

            # 16.1 校验字段格式，非空
            if not review_config or not isinstance(review_config, dict):
                raise ValidateErrorException("审核配置格式错误")
            # 16.2 校验字段信息
            if set(review_config.keys()) != {"enable", "keywords", "inputs_config", "outputs_config"}:
                raise ValidateErrorException("审核配置格式错误")
            # 16.3 校验enable
            if not isinstance(review_config["enable"], bool):
                raise ValidateErrorException("review.enable格式错误")
            # 16.4 校验keywords
            if (
                    not isinstance(review_config["keywords"], list)
                    or (review_config["enable"] and len(review_config["keywords"]) == 0)
                    or len(review_config["keywords"]) > 100
            ):
                raise ValidateErrorException("review.keywords非空且不能超过100个关键词")
            for keyword in review_config["keywords"]:
                if not isinstance(keyword, str):
                    raise ValidateErrorException("review.keywords敏感词必须是字符串")
            # 16.5 校验inputs_config输入配置
            if (
                    not review_config["inputs_config"]
                    or not isinstance(review_config["inputs_config"], dict)
                    or set(review_config["inputs_config"].keys()) != {"enable", "preset_response"}
                    or not isinstance(review_config["inputs_config"]["enable"], bool)
                    or not isinstance(review_config["inputs_config"]["preset_response"], str)
            ):
                raise ValidateErrorException("review.inputs_config必须是一个字典")
            # 16.6 校验outputs_config输出配置
            if (
                    not review_config["outputs_config"]
                    or not isinstance(review_config["outputs_config"], dict)
                    or set(review_config["outputs_config"].keys()) != {"enable"}
                    or not isinstance(review_config["outputs_config"]["enable"], bool)
            ):
                raise ValidateErrorException("review.outputs_config格式错误")
            # 16.7 在开启审核模块的时候，必须确保inputs_config或者是outputs_config至少有一个是开启的
            if review_config["enable"]:
                if (
                        review_config["inputs_config"]["enable"] is False
                        and review_config["outputs_config"]["enable"] is False
                ):
                    raise ValidateErrorException("输入审核和输出审核至少需要开启一项")

                if (
                        review_config["inputs_config"]["enable"]
                        and review_config["inputs_config"]["preset_response"].strip() == ""
                ):
                    raise ValidateErrorException("输入审核预设响应不能为空")

        # 18.校验Agent绑定
        if "agent_bindings" in draft_app_config:
            if app_id is None:
                raise ValidateErrorException("Agent绑定校验缺少应用ID")

            agent_bindings = draft_app_config["agent_bindings"]
            if not isinstance(agent_bindings, list):
                raise ValidateErrorException("Agent绑定列表必须是列表型数据")

            _, validate_agent_bindings = self.app_config_service.process_and_validate_agent_bindings(
                agent_bindings,
                current_account_id=account.id,
                current_app_id=app_id,
                strict=True,
            )
            draft_app_config["agent_bindings"] = validate_agent_bindings

        return draft_app_config

    def _generate_default_icon(self, app_name: str) -> str:
        """
        生成一个默认的彩色SVG图标

        Args:
            app_name: 应用名称

        Returns:
            str: 图标的COS URL或数据URI
        """
        import hashlib

        # 使用应用名称生成一个稳定的颜色
        hash_obj = hashlib.md5(app_name.encode())
        hash_hex = hash_obj.hexdigest()

        # 从哈希值中提取RGB颜色
        r = int(hash_hex[0:2], 16)
        g = int(hash_hex[2:4], 16)
        b = int(hash_hex[4:6], 16)

        # 确保颜色足够亮
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        if brightness < 100:
            r = min(255, r + 100)
            g = min(255, g + 100)
            b = min(255, b + 100)

        # 获取应用名称的首字母
        first_char = app_name[0].upper() if app_name else "A"

        # 创建SVG图标
        svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <rect width="200" height="200" fill="rgb({r},{g},{b})" rx="40"/>
  <text x="100" y="120" font-size="100" font-weight="bold" fill="white" text-anchor="middle" font-family="Arial, sans-serif">{first_char}</text>
</svg>'''

        # 将SVG转换为数据URI
        import base64
        svg_bytes = svg_content.encode('utf-8')
        svg_base64 = base64.b64encode(svg_bytes).decode('utf-8')
        data_uri = f"data:image/svg+xml;base64,{svg_base64}"

        return data_uri
