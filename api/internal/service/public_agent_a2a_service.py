import json
import logging
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from flask import Flask, current_app, has_app_context
from injector import inject
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from internal.entity.app_entity import AppStatus
from internal.exception import NotFoundException, ValidateErrorException
from internal.model import App
from pkg.sqlalchemy import SQLAlchemy

from .app_config_service import AppConfigService
from .app_service import AppService
from .base_service import BaseService
from .language_model_service import LanguageModelService
from .public_agent_registry_service import PublicAgentRegistryService


@inject
@dataclass
class PublicAgentA2AService(BaseService):
    """公共Agent的A2A协议服务。"""

    db: SQLAlchemy
    app_service: AppService
    app_config_service: AppConfigService
    language_model_service: LanguageModelService
    public_agent_registry_service: PublicAgentRegistryService

    def convert_public_agent_route_to_tool(self, account_id: UUID) -> BaseTool:
        """将公共Agent路由能力转换成LangChain工具。"""
        flask_app = current_app._get_current_object() if has_app_context() else None
        assistant_agent_id = ""
        if flask_app is not None:
            assistant_agent_id = str(flask_app.config.get("ASSISTANT_AGENT_ID", "")).strip()

        class PublicAgentRouteInput(BaseModel):
            """公共Agent路由工具输入结构"""

            query: str = Field(description="需要委派给公共Agent处理的用户问题")

        @tool("route_public_agents", args_schema=PublicAgentRouteInput)
        def route_public_agents(query: str) -> dict[str, Any]:
            """当用户明确要求使用某个已有智能体回答，或当前问题更适合交给已发布公共/垂直/Agent这样的细分具体问题处理时，优先调用该工具。它会先检索公开Agent，再筛选出真正相关的候选，最后按A2A协议依次调用，最多返回3个相关Agent的结果。对于“请使用xx智能体回答”“让xxAgent来回答”“帮我解决xx”“帮我解决xx等垂直问题”等这类请求，必须优先使用本工具，禁止改用 `create_app` 新建应用。"""
            if flask_app is not None and not has_app_context():
                with flask_app.app_context():
                    return self.route_public_agents(
                        query=query,
                        caller_account_id=account_id,
                        assistant_agent_id=assistant_agent_id,
                        flask_app=flask_app,
                    )

            return self.route_public_agents(
                query=query,
                caller_account_id=account_id,
                assistant_agent_id=assistant_agent_id,
                flask_app=flask_app,
            )

        return route_public_agents

    def route_public_agents(
        self,
        query: str,
        caller_account_id: UUID,
        limit: int = 3,
        assistant_agent_id: str = "",
        flask_app: Flask | None = None,
    ) -> dict[str, Any]:
        """先检索，再委派公开Agent处理问题。"""
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return {"matches": [], "delegated_results": [], "message": "用户问题为空，无法委派公共Agent"}

        resolved_assistant_agent_id = str(assistant_agent_id or "").strip()
        if not resolved_assistant_agent_id and has_app_context():
            resolved_assistant_agent_id = str(current_app.config.get("ASSISTANT_AGENT_ID", "")).strip()
        matches = self.public_agent_registry_service.search_public_apps(
            query=normalized_query,
            limit=limit,
            metadata_filter={"is_public": True},
            exclude_app_ids=[resolved_assistant_agent_id] if resolved_assistant_agent_id else [],
        )

        selected_matches, filtered_out_matches, selection_reason = self._select_relevant_matches(
            query=normalized_query,
            matches=matches,
            limit=limit,
        )

        delegated_results = []
        for match in selected_matches:
            try:
                response = self.send_message(
                    app_id=match["app_id"],
                    payload={
                        "message": {
                            "role": "user",
                            "parts": [{"type": "text", "text": normalized_query}],
                        },
                        "metadata": {"caller_account_id": str(caller_account_id)},
                    },
                    flask_app=flask_app,
                )
                delegated_results.append(
                    {
                        "app_id": match["app_id"],
                        "name": match["name"],
                        "description": match["description"],
                        "a2a_card_url": match["a2a_card_url"],
                        "a2a_message_url": match["a2a_message_url"],
                        "answer": self._extract_answer_text(response),
                        "status": response.get("metadata", {}).get("status", ""),
                        "error": response.get("metadata", {}).get("error", ""),
                    }
                )
            except Exception as exc:
                delegated_results.append(
                    {
                        "app_id": match["app_id"],
                        "name": match["name"],
                        "description": match["description"],
                        "a2a_card_url": match["a2a_card_url"],
                        "a2a_message_url": match["a2a_message_url"],
                        "answer": "",
                        "status": "error",
                        "error": str(exc),
                    }
                )

        return {
            "matches": matches,
            "selected_matches": selected_matches,
            "filtered_out_matches": filtered_out_matches,
            "delegated_results": delegated_results,
            "selection_reason": selection_reason,
            "message": (
                "已筛选并委派相关公共Agent"
                if selected_matches
                else "未找到足够相关的公共Agent"
            ),
        }

    def _select_relevant_matches(
        self,
        query: str,
        matches: list[dict[str, Any]],
        limit: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
        """从召回候选中筛选真正相关的公开Agent。"""
        if not matches:
            return [], [], "未检索到公共Agent候选"

        normalized_limit = max(1, min(int(limit or 3), 3))
        if len(matches) == 1:
            return matches[:1], [], "仅检索到1个候选公共Agent，直接委派"

        explicit_matches = self._find_explicit_name_matches(query, matches, normalized_limit)
        if explicit_matches:
            explicit_ids = {str(match.get("app_id", "")).strip() for match in explicit_matches}
            filtered_out_matches = [
                match for match in matches if str(match.get("app_id", "")).strip() not in explicit_ids
            ]
            return explicit_matches, filtered_out_matches, "根据用户显式提及的Agent名称完成筛选"

        selected_app_ids, selection_reason = self._select_relevant_agent_ids_with_llm(
            query=query,
            matches=matches,
            limit=normalized_limit,
        )
        selected_id_set = {app_id for app_id in selected_app_ids if app_id}
        selected_matches = [
            match for match in matches
            if str(match.get("app_id", "")).strip() in selected_id_set
        ][:normalized_limit]
        filtered_out_matches = [
            match for match in matches
            if str(match.get("app_id", "")).strip() not in selected_id_set
        ]

        if selected_matches:
            return (
                selected_matches,
                filtered_out_matches,
                selection_reason or "模型已筛选出相关公共Agent",
            )

        return [], matches, selection_reason or "模型未筛选出足够相关的公共Agent"

    def _select_relevant_agent_ids_with_llm(
        self,
        query: str,
        matches: list[dict[str, Any]],
        limit: int,
    ) -> tuple[list[str], str]:
        """使用模型对召回候选做二次相关性判断。"""
        candidate_ids = [
            str(match.get("app_id", "")).strip()
            for match in matches
            if str(match.get("app_id", "")).strip()
        ]
        if not candidate_ids:
            return [], "候选公共Agent缺少有效app_id"

        try:
            llm = self.language_model_service.load_default_language_model()
            if hasattr(llm, "temperature"):
                llm.temperature = 0

            class PublicAgentSelectionOutput(BaseModel):
                """公开Agent筛选输出结构"""

                selected_app_ids: list[str] = Field(
                    default_factory=list,
                    description="真正应该被调用的公共Agent app_id列表；不相关时返回空列表",
                )
                reason: str = Field(
                    default="",
                    description="简短说明筛选原因，强调为什么保留或过滤这些候选",
                )

            @tool("select_public_agents", args_schema=PublicAgentSelectionOutput)
            def select_public_agents(selected_app_ids: list[str], reason: str = "") -> str:
                """从候选公共Agent里选择真正相关且值得委派的Agent。"""
                return reason or "ok"

            system_prompt, human_prompt = self._build_agent_selection_prompt(query, matches, limit)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt),
            ]

            if hasattr(llm, "bind_tools") and callable(getattr(llm, "bind_tools")):
                response = llm.bind_tools([select_public_agents]).invoke(messages)
                selected_app_ids, reason = self._extract_agent_selection_from_response(
                    response=response,
                    candidate_ids=candidate_ids,
                    limit=limit,
                )
                if selected_app_ids or reason:
                    return selected_app_ids, reason

            response = llm.invoke(messages)
            return self._extract_agent_selection_from_response(
                response=response,
                candidate_ids=candidate_ids,
                limit=limit,
            )
        except Exception as exc:
            logging.exception("公开Agent二次筛选失败: %s", str(exc))
            return [], f"模型筛选失败: {str(exc)}"

    @classmethod
    def _build_agent_selection_prompt(
        cls,
        query: str,
        matches: list[dict[str, Any]],
        limit: int,
    ) -> tuple[str, str]:
        """构建公共Agent二次筛选提示词。"""
        candidates = [
            {
                "app_id": str(match.get("app_id", "")).strip(),
                "name": str(match.get("name", "")).strip(),
                "description": str(match.get("description", "")).strip(),
                "tags": match.get("tags", []) or [],
                "page_content": str(match.get("page_content", "")).strip(),
            }
            for match in matches
        ]
        system_prompt = (
            "你是公共Agent路由裁决器。"
            "你的任务是从候选公共Agent中筛选出真正应该被调用的Agent。"
            "请严格遵守以下规则：\n"
            "1. 只选择能够直接回答、处理或覆盖用户问题核心意图的Agent。\n"
            "2. 不要因为候选是向量检索召回结果就默认相关。\n"
            "3. 对明显无关、仅有弱关联或只是泛泛可聊的Agent，必须过滤掉。\n"
            "4. 只有当多个Agent分别覆盖用户请求中不同且必要的部分时，才允许多选。\n"
            "5. 如果没有足够相关的Agent，可以返回空列表。\n"
            "6. 输出时优先调用 select_public_agents 工具；若不能调用工具，则输出JSON对象，字段为 selected_app_ids 和 reason。"
        )
        human_prompt = (
            f"用户问题:\n{query}\n\n"
            f"最多可选择的Agent数量: {limit}\n\n"
            "候选公共Agent列表:\n"
            f"{json.dumps(candidates, ensure_ascii=False, indent=2)}"
        )
        return system_prompt, human_prompt

    @classmethod
    def _extract_agent_selection_from_response(
        cls,
        response: Any,
        candidate_ids: list[str],
        limit: int,
    ) -> tuple[list[str], str]:
        """从模型响应中提取筛选结果。"""
        selected_app_ids, reason = cls._extract_agent_selection_from_tool_calls(
            response=response,
            candidate_ids=candidate_ids,
            limit=limit,
        )
        if selected_app_ids or reason:
            return selected_app_ids, reason

        response_text = cls._extract_model_response_text(response)
        if not response_text:
            return [], ""

        payload = cls._extract_json_object(response_text)
        if not isinstance(payload, dict):
            return [], response_text.strip()

        selected_app_ids = cls._normalize_selected_app_ids(
            payload.get("selected_app_ids", []),
            candidate_ids=candidate_ids,
            limit=limit,
        )
        return selected_app_ids, str(payload.get("reason", "")).strip()

    @classmethod
    def _extract_agent_selection_from_tool_calls(
        cls,
        response: Any,
        candidate_ids: list[str],
        limit: int,
    ) -> tuple[list[str], str]:
        """优先从工具调用结果中提取筛选输出。"""
        tool_calls = getattr(response, "tool_calls", []) or []
        for tool_call in tool_calls:
            if str(tool_call.get("name", "")).strip() != "select_public_agents":
                continue
            args = tool_call.get("args", {}) or {}
            if isinstance(args, str):
                parsed_args = cls._extract_json_object(args)
                args = parsed_args if isinstance(parsed_args, dict) else {}
            if not isinstance(args, dict):
                continue
            selected_app_ids = cls._normalize_selected_app_ids(
                args.get("selected_app_ids", []),
                candidate_ids=candidate_ids,
                limit=limit,
            )
            return selected_app_ids, str(args.get("reason", "")).strip()
        return [], ""

    @classmethod
    def _normalize_selected_app_ids(
        cls,
        selected_app_ids: Any,
        candidate_ids: list[str],
        limit: int,
    ) -> list[str]:
        """规范化并过滤模型返回的 app_id 列表。"""
        candidate_id_set = set(candidate_ids)
        normalized_ids = []
        seen = set()
        for raw_app_id in selected_app_ids if isinstance(selected_app_ids, list) else []:
            app_id = str(raw_app_id or "").strip()
            if not app_id or app_id not in candidate_id_set or app_id in seen:
                continue
            seen.add(app_id)
            normalized_ids.append(app_id)
            if len(normalized_ids) >= limit:
                break
        return normalized_ids

    @classmethod
    def _extract_model_response_text(cls, response: Any) -> str:
        """从模型响应中提取纯文本。"""
        if isinstance(response, str):
            return response.strip()

        content = getattr(response, "content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_fragments = []
            for item in content:
                if isinstance(item, str):
                    text_fragments.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text", "")).strip()
                if text:
                    text_fragments.append(text)
            return "\n".join(text_fragments).strip()
        return str(content).strip()

    @classmethod
    def _extract_json_object(cls, text: str) -> dict[str, Any] | None:
        """从文本中提取第一个JSON对象。"""
        normalized_text = str(text or "").strip()
        if not normalized_text:
            return None

        for candidate in (normalized_text, cls._strip_markdown_code_fence(normalized_text)):
            try:
                payload = json.loads(candidate)
            except Exception:
                payload = None
            if isinstance(payload, dict):
                return payload

        match = re.search(r"\{[\s\S]*\}", normalized_text)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    @classmethod
    def _strip_markdown_code_fence(cls, text: str) -> str:
        """移除包裹JSON的Markdown代码块围栏。"""
        normalized_text = str(text or "").strip()
        if normalized_text.startswith("```") and normalized_text.endswith("```"):
            lines = normalized_text.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return normalized_text

    @classmethod
    def _find_explicit_name_matches(
        cls,
        query: str,
        matches: list[dict[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        """优先处理用户显式点名的公共Agent。"""
        normalized_query = cls._normalize_text_for_match(query)
        if not normalized_query:
            return []

        selected_matches = []
        for match in matches:
            name = str(match.get("name", "")).strip()
            normalized_name = cls._normalize_text_for_match(name)
            if not normalized_name:
                continue
            if normalized_name not in normalized_query:
                continue
            selected_matches.append(match)
            if len(selected_matches) >= limit:
                break
        return selected_matches

    @classmethod
    def _normalize_text_for_match(cls, text: str) -> str:
        """归一化文本，便于做显式名称匹配。"""
        return re.sub(r"[\s\-_`~!@#$%^&*()+={}\[\]|\\:;\"'<>,.?/，。！？、；：（）【】《》“”‘’]+", "", str(text or "")).lower()

    def get_agent_card(self, app_id: UUID | str) -> dict[str, Any]:
        """返回公开Agent的A2A Agent Card。"""
        app = self._get_public_app(app_id)
        app_config = self.app_config_service.get_app_config(app)
        message_url = self.public_agent_registry_service.build_agent_message_url(app.id)
        card_url = self.public_agent_registry_service.build_agent_card_url(app.id)

        return {
            "name": app.name,
            "description": app.description,
            "version": "1.0",
            "protocolVersion": "1.0",
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": False,
            },
            "supportedInterfaces": [
                {
                    "url": message_url,
                    "protocolBinding": "HTTP+JSON/REST",
                    "protocolVersion": "1.0",
                }
            ],
            "skills": [
                {
                    "id": str(app.id),
                    "name": app.name,
                    "description": app.description or app_config.get("opening_statement", ""),
                    "tags": app.tags or [],
                    "examples": app_config.get("opening_questions", [])[:3],
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain"],
                }
            ],
            "a2aCardUrl": card_url,
            "a2aMessageUrl": message_url,
        }

    def send_message(
        self,
        app_id: UUID | str,
        payload: dict[str, Any] | None,
        flask_app: Flask | None = None,
    ) -> dict[str, Any]:
        """以A2A消息格式调用指定公开Agent。"""
        app = self._get_public_app(app_id)
        request_payload = payload or {}
        query = self._extract_query_from_payload(request_payload)
        if not query:
            raise ValidateErrorException("A2A消息中缺少可用的文本内容")

        context_id = (
            str(request_payload.get("contextId", "")).strip()
            or str(request_payload.get("context_id", "")).strip()
            or str(app.id)
        )
        agent_result = self._invoke_public_agent(app, query, flask_app=flask_app)

        return {
            "contextId": context_id,
            "message": {
                "role": "agent",
                "parts": [{"type": "text", "text": agent_result.answer}],
            },
            "artifacts": [],
            "metadata": {
                "app_id": str(app.id),
                "status": agent_result.status,
                "error": agent_result.error,
            },
        }

    def _invoke_public_agent(
        self,
        app: App,
        query: str,
        flask_app: Flask | None = None,
    ):
        """以内存方式调用公开Agent，不落库。"""
        app_config = self.app_config_service.get_app_config(app)
        llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))
        owner_account = SimpleNamespace(id=app.account_id)
        tools = self.app_service._build_runtime_tools(
            app.id,
            owner_account,
            app_config,
            flask_app=flask_app,
        )
        agent = self.app_service._create_runtime_agent(llm, owner_account, app_config, tools)
        return agent.invoke(
            {
                "messages": [llm.convert_to_human_message(query, [])],
                "history": [],
                "long_term_memory": "",
            }
        )

    def _get_public_app(self, app_id: UUID | str) -> App:
        """获取已发布且公开的应用。"""
        try:
            app_uuid = UUID(str(app_id))
        except Exception as exc:
            raise NotFoundException("公共Agent不存在") from exc

        app = self.db.session.query(App).filter(
            App.id == app_uuid,
            App.status == AppStatus.PUBLISHED.value,
            App.is_public == True,
        ).one_or_none()
        if not app:
            raise NotFoundException("公共Agent不存在或未公开")
        return app

    @classmethod
    def _extract_query_from_payload(cls, payload: dict[str, Any]) -> str:
        """从A2A payload中提取用户问题。"""
        direct_query = str(payload.get("query", "")).strip()
        if direct_query:
            return direct_query

        message = payload.get("message", {})
        if not isinstance(message, dict):
            return ""

        parts = message.get("parts", [])
        if not isinstance(parts, list):
            return ""

        for part in parts:
            if not isinstance(part, dict):
                continue
            if str(part.get("type", "")).strip() != "text":
                continue
            text = str(part.get("text", "")).strip()
            if text:
                return text

        return ""

    @classmethod
    def _extract_answer_text(cls, response: dict[str, Any]) -> str:
        """从A2A响应中提取文本答案。"""
        message = response.get("message", {})
        if not isinstance(message, dict):
            return ""
        parts = message.get("parts", [])
        if not isinstance(parts, list):
            return ""
        for part in parts:
            if not isinstance(part, dict):
                continue
            if str(part.get("type", "")).strip() != "text":
                continue
            text = str(part.get("text", "")).strip()
            if text:
                return text
        return ""
