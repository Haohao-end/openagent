import json
import logging
import os
import re
import time
import uuid
from typing import Literal, Any, ClassVar

import tiktoken
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, RemoveMessage, AIMessage
from langchain_core.messages import messages_to_dict
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from internal.core.agent.entities.agent_entity import (
    AgentState,
    AGENT_SYSTEM_PROMPT_TEMPLATE,
    MAX_ITERATION_RESPONSE,
)
from internal.core.agent.entities.sandbox_policy_entity import SandboxPolicy
from internal.core.agent.entities.tool_policy_entity import ToolPolicy
from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.agent.usage_utils import normalize_usage_text
from internal.exception import FailException
from .base_agent import BaseAgent
from internal.core.language_model.entities.model_entity import ModelFeature


class FunctionCallAgent(BaseAgent):
    """基于函数/工具调用的智能体"""

    _PROMPT_ONLY_SKILL_LOADER_PREFIX: ClassVar[str] = "skill_prompt__"

    def _build_agent(self) -> CompiledStateGraph:
        """构建LangGraph图结构编译程序"""
        # 1.创建图
        graph = StateGraph(AgentState)

        # 2.添加节点
        graph.add_node("preset_operation", self._preset_operation_node)
        graph.add_node("long_term_memory_recall", self._long_term_memory_recall_node)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tools", self._tools_node)

        # 3.添加边，并设置起点和终点
        graph.set_entry_point("preset_operation")
        graph.add_conditional_edges("preset_operation", self._preset_operation_condition)
        graph.add_edge("long_term_memory_recall", "llm")
        graph.add_conditional_edges("llm", self._tools_condition)
        graph.add_edge("tools", "llm")

        # 4.编译应用并返回
        agent = graph.compile()

        return agent

    @classmethod
    def _sanitize_sandbox_artifact_text(cls, content: str) -> str:
        """去除用户可见文本中的沙箱本地路径与伪下载链接。"""
        return SandboxPolicy.sanitize_sandbox_artifact_text(content)

    def _preset_operation_node(self, state: AgentState) -> AgentState:
        """预设操作，涵盖：输入审核、数据预处理、条件边等"""
        # 1.获取审核配置与用户输入query
        review_config = self.agent_config.review_config
        query = state["messages"][-1].content

        # 2.检测是否开启审核配置
        if review_config["enable"] and review_config["inputs_config"]["enable"]:
            contains_keyword = any(keyword in query for keyword in review_config["keywords"])
            # 3.如果包含敏感词则执行后续步骤
            if contains_keyword:
                preset_response = review_config["inputs_config"]["preset_response"]
                self.agent_queue_manager.publish(state["task_id"], AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_MESSAGE.value,
                    thought=preset_response,
                    message=messages_to_dict(state["messages"]),
                    answer=preset_response,
                    latency=0,
                ))
                self.agent_queue_manager.publish(state["task_id"], AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END.value,
                ))
                return {"messages": [AIMessage(preset_response)]}

        return {"messages": []}

    def _long_term_memory_recall_node(self, state: AgentState) -> AgentState:
        """长期记忆召回节点"""
        # 1.根据传递的智能体配置判断是否需要召回长期记忆
        long_term_memory = ""
        if self.agent_config.enable_long_term_memory:
            long_term_memory = state["long_term_memory"]
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.LONG_TERM_MEMORY_RECALL.value,
                observation=long_term_memory,
            ))

        # 2.构建预设消息列表，并将preset_prompt+long_term_memory填充到系统消息中
        preset_messages = [
            SystemMessage(AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                preset_prompt=self.agent_config.preset_prompt,
                long_term_memory=long_term_memory,
            ))
        ]

        # 3.将短期历史消息添加到消息列表中
        history = state["history"]
        if isinstance(history, list) and len(history) > 0:
            # 4.校验历史消息是不是复数形式，也就是[人类消息, AI消息, 人类消息, AI消息, ...]
            if len(history) % 2 != 0:
                self.agent_queue_manager.publish_error(state["task_id"], "智能体历史消息列表格式错误")
                logging.exception(
                    f"智能体历史消息列表格式错误, len(history)={len(history)}, history={json.dumps(messages_to_dict(history))}"
                )
                raise FailException("智能体历史消息列表格式错误")
            # 5.拼接历史消息
            preset_messages.extend(history)

        # 6.拼接当前用户的提问信息
        human_message = state["messages"][-1]
        preset_messages.append(HumanMessage(human_message.content))

        # 7.处理预设消息，将预设消息添加到用户消息前，先去删除用户的原始消息，然后补充一个新的代替
        return {
            "messages": [RemoveMessage(id=human_message.id), *preset_messages],
        }

    def _llm_node(self, state: AgentState) -> AgentState:
        """大语言模型节点"""
        # 1.检测当前Agent迭代次数是否符合需求
        if state["iteration_count"] > self.agent_config.max_iteration_count:
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_MESSAGE.value,
                    thought=MAX_ITERATION_RESPONSE,
                    message=messages_to_dict(state["messages"]),
                    answer=MAX_ITERATION_RESPONSE,
                    latency=0,
                ))
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END.value,
                ))
            return {"messages": [AIMessage(MAX_ITERATION_RESPONSE)], "pending_skill_prompts": []}

        # 2.从智能体配置中提取大语言模型
        id = uuid.uuid4()
        start_at = time.perf_counter()
        llm = self.llm
        pending_skill_prompts = self._deduplicate_pending_skill_prompts(state.get("pending_skill_prompts") or [])
        llm_messages = self._inject_pending_skill_prompts(state["messages"], pending_skill_prompts)

        # 3.检测大语言模型实例是否有bind_tools方法，如果没有则不绑定，如果有还需要检测tools是否为空，不为空则绑定
        if (
            ModelFeature.TOOL_CALL.value in llm.features
            and hasattr(llm, "bind_tools")
            and callable(getattr(llm, "bind_tools"))
            and len(self.agent_config.tools) > 0
        ):
            llm = llm.bind_tools(self.agent_config.tools)

        # 4.流式调用LLM输出对应内容
        gathered = None
        buffered_text_chunks: list[str] = []
        saw_tool_calls = False
        try:
            for chunk in llm.stream(llm_messages):
                if chunk is None:  # 跳过无效 chunk
                    continue
                if gathered is None:
                    gathered = chunk
                else:
                    gathered += chunk
                    if gathered is None:  # 防止部分chunk合并实现返回None
                        gathered = chunk

                if getattr(chunk, "tool_calls", None):
                    saw_tool_calls = True

                content = self._normalize_chunk_content(getattr(chunk, "content", ""))
                if content:
                    buffered_text_chunks.append(self._apply_output_review(content))
        except Exception as e:
            logging.exception(f"LLM节点发生错误, 错误信息: {str(e)}")
            self.agent_queue_manager.publish_failure(
                state["task_id"],
                e,
                context="LLM节点发生错误",
            )
            raise

        if gathered is None:
            if pending_skill_prompts:
                logger.info(
                    "技能 prompt 租约已回收: lease_ids=%s",
                    [
                        str(item.get("lease_id") or item.get("skill_id") or item.get("source_key") or "")
                        for item in pending_skill_prompts
                        if isinstance(item, dict)
                    ],
                )
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.AGENT_END.value,
            ))
            return {
                "messages": [AIMessage(content="")],
                "iteration_count": state["iteration_count"] + 1,
                "pending_skill_prompts": [],
            }

        # 8.计算LLM的输入+输出的token总数
        input_token_count, output_token_count, total_token_count, total_price, unit, input_price, output_price = (
            self._calculate_usage(state, gathered, messages=llm_messages)
        )

        # 11.如果类型为推理则添加智能体推理事件
        final_tool_calls = getattr(gathered, "tool_calls", []) or []
        # 某些流式实现会先在中间 chunk 暴露 tool_calls，再在最终聚合对象里补齐。
        if saw_tool_calls or final_tool_calls:
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_THOUGHT.value,
                thought=json.dumps(final_tool_calls),
                # 消息相关字段
                message=messages_to_dict(state["messages"]),
                message_token_count=input_token_count,  # 消息花费的token数
                message_unit_price=input_price,  # 单价
                message_price_unit=unit,  # 价格单位
                # 答案相关字段
                answer="",
                answer_token_count=output_token_count,
                answer_unit_price=output_price,
                answer_price_unit=unit,
                # Agent推理相关字段
                total_token_count=total_token_count,
                total_price=total_price,
                latency=(time.perf_counter() - start_at),
            ))
            return {
                "messages": [gathered],
                "iteration_count": state["iteration_count"] + 1,
                "pending_skill_prompts": [],
            }

        final_content = self._finalize_llm_output(state, "".join(buffered_text_chunks))
        final_content = self._postprocess_llm_output(state, final_content)
        self.agent_queue_manager.publish(state["task_id"], AgentThought(
            id=id,
            task_id=state["task_id"],
            event=QueueEvent.AGENT_MESSAGE.value,
            thought=final_content,
            message=messages_to_dict(state["messages"]),
            answer=final_content,
            latency=(time.perf_counter() - start_at),
        ))

        if not final_tool_calls:
            if pending_skill_prompts:
                logger.info(
                    "技能 prompt 租约已回收: lease_ids=%s",
                    [
                        str(item.get("lease_id") or item.get("skill_id") or item.get("source_key") or "")
                        for item in pending_skill_prompts
                        if isinstance(item, dict)
                    ],
                )
            # 12.如果LLM直接生成answer则表示已经拿到了最终答案，推送一条空内容用于计算总token+总成本,则停止监听
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_MESSAGE.value,
                thought="",
                # 消息相关字段
                message=messages_to_dict(state["messages"]),
                message_token_count=input_token_count,  # 消息花费的token数
                message_unit_price=input_price,  # 单价
                message_price_unit=unit,  # 价格单位
                # 答案相关字段
                answer="",
                answer_token_count=output_token_count,
                answer_unit_price=output_price,
                answer_price_unit=unit,
                # Agent推理相关字段
                total_token_count=total_token_count,
                total_price=total_price,
                latency=(time.perf_counter() - start_at),
            ))
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.AGENT_END.value,
            ))

        return {
            "messages": [AIMessage(content=final_content)],
            "iteration_count": state["iteration_count"] + 1,
            "pending_skill_prompts": [],
        }

    def _finalize_llm_output(self, state: AgentState, content: str) -> str:
        """把最终输出收口成用户可见文本。"""
        return self._sanitize_sandbox_artifact_text(self._apply_output_review(content))

    def _postprocess_llm_output(self, state: AgentState, content: str) -> str:
        """给最终输出留一个可覆写的后处理钩子。"""
        return content

    def _tools_node(self, state: AgentState) -> AgentState:
        """工具执行节点"""
        # 1.将工具列表转换成字典，便于调用指定的工具
        tool_policy = getattr(self.agent_config, "tool_policy", None) or ToolPolicy()
        tools_by_name = {tool.name: tool for tool in self.agent_config.tools}
        tools_by_alias = {}
        for tool in self.agent_config.tools:
            alias = self._normalize_tool_alias(tool.name)
            if alias and alias not in tools_by_alias:
                tools_by_alias[alias] = tool

        # 2.提取消息中的工具调用参数
        tool_calls = state["messages"][-1].tool_calls

        # 3.循环执行工具组装工具消息
        messages = []
        pending_skill_prompts = self._deduplicate_pending_skill_prompts(state.get("pending_skill_prompts") or [])
        pending_prompt_keys = {
            self._prompt_only_skill_identity_key(item)
            for item in pending_skill_prompts
            if isinstance(item, dict)
        }
        for tool_call in tool_calls:
            # 4.创建智能体动作事件id并记录开始时间
            id = uuid.uuid4()
            start_at = time.perf_counter()

            tool = None
            try:
                # 5.获取工具并调用工具
                tool = self._resolve_tool(tool_call["name"], tools_by_name, tools_by_alias)
                if tool is None:
                    raise LookupError(self._build_tool_not_found_result(tool_call["name"], tools_by_name))
                tool_result = tool.invoke(tool_call["args"])
            except LookupError as e:
                if tool is not None and tool_policy.is_hard_fail_tool(tool_call["name"]):
                    self.agent_queue_manager.publish_failure(
                        state["task_id"], e, context=f"{tool_call['name']}执行失败"
                    )
                    raise
                tool_result = str(e)
            except Exception as e:
                if tool_policy.is_hard_fail_tool(tool_call["name"]):
                    self.agent_queue_manager.publish_failure(
                        state["task_id"],
                        e,
                        context=f"{tool_call['name']}执行失败",
                    )
                    raise
                # 6.添加错误工具信息
                tool_result = f"工具执行出错: {str(e)}"

            public_tool_result = tool_result
            prompt_lease = None
            if self._is_prompt_only_skill_loader_tool(tool_call["name"]):
                public_tool_result, prompt_lease = self._build_prompt_only_skill_loader_result(tool_result)
                if prompt_lease:
                    prompt_key = self._prompt_only_skill_identity_key(prompt_lease)
                    if prompt_key and prompt_key not in pending_prompt_keys:
                        pending_skill_prompts.append(prompt_lease)
                        pending_prompt_keys.add(prompt_key)

            serialized_tool_result = (
                public_tool_result
                if isinstance(public_tool_result, str)
                else json.dumps(public_tool_result, ensure_ascii=False, default=str)
            )

            # 7.将工具消息添加到消息列表中
            messages.append(ToolMessage(
                tool_call_id=tool_call["id"],
                content=serialized_tool_result,
                name=tool_call["name"],
            ))

            # 7.判断执行工具的名字，提交不同事件，涵盖智能体动作以及知识库检索
            event = (
                QueueEvent.AGENT_ACTION.value
                if tool_policy.resolve_tool_name(tool_call["name"])
                != tool_policy.resolve_tool_name(tool_policy.dataset_retrieval_tool_name)
                else QueueEvent.DATASET_RETRIEVAL.value
            )
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=id,
                task_id=state["task_id"],
                event=event,
                observation=serialized_tool_result,
                tool=tool_call["name"],
                tool_input=tool_call["args"],
                latency=(time.perf_counter() - start_at),
            ))

        return {
            "messages": messages,
            "pending_skill_prompts": pending_skill_prompts,
        }

    @staticmethod
    def _build_tool_not_found_result(tool_call_name: str, tools_by_name: dict[str, Any]) -> str:
        """把可用工具名回灌给模型，促使其基于真实列表重新选择。"""
        available_tool_names = list(tools_by_name.keys())
        preview_limit = 30
        preview = available_tool_names[:preview_limit]
        suffix = ""
        if len(available_tool_names) > preview_limit:
            suffix = f" 等共 {len(available_tool_names)} 个工具"
        available_text = ", ".join(preview) if preview else "无"
        return (
            f"工具未找到: {tool_call_name}。"
            f"请从当前可用工具列表中重新选择并调用: {available_text}{suffix}。"
        )

    def _resolve_tool(
        self,
        tool_call_name: str,
        tools_by_name: dict[str, Any],
        tools_by_alias: dict[str, Any],
    ) -> Any | None:
        """按精确名、别名顺序解析工具。"""
        tool_policy = getattr(self.agent_config, "tool_policy", None) or ToolPolicy()
        requested_name = tool_policy.resolve_tool_name(tool_call_name)

        candidates = (
            requested_name,
        )
        for candidate in candidates:
            if not candidate:
                continue
            tool = tools_by_name.get(candidate)
            if tool is not None:
                return tool

            tool = tools_by_alias.get(candidate)
            if tool is not None:
                return tool

        return None

    @staticmethod
    def _normalize_tool_alias(tool_name: str | None) -> str:
        if not tool_name:
            return ""

        normalized = str(tool_name).strip()
        if not normalized:
            return ""

        parts = normalized.split("__", 2)
        if len(parts) == 3:
            return parts[2]
        return normalized.replace("-", "_").replace(" ", "_")

    @classmethod
    def _is_prompt_only_skill_loader_tool(cls, tool_name: str | None) -> bool:
        return str(tool_name or "").startswith(cls._PROMPT_ONLY_SKILL_LOADER_PREFIX)

    @staticmethod
    def _build_prompt_only_skill_loader_result(tool_result: Any) -> tuple[Any, dict[str, Any] | None]:
        """把 prompt-only 技能全文加载结果拆成公开结果与待注入全文。"""
        if not isinstance(tool_result, dict):
            return tool_result, None

        prompt_text = str(tool_result.get("prompt") or tool_result.get("readme") or "").strip()
        if not prompt_text:
            return tool_result, None

        public_result = {
            "skill_id": str(tool_result.get("skill_id") or "").strip(),
            "source_key": str(tool_result.get("source_key") or "").strip(),
            "name": str(tool_result.get("name") or "").strip(),
            "label": str(tool_result.get("label") or "").strip(),
            "description": str(tool_result.get("description") or "").strip(),
            "category": str(tool_result.get("category") or "").strip(),
            "executor_type": str(tool_result.get("executor_type") or "").strip(),
            "prompt_length": len(prompt_text),
            "lease_id": str(tool_result.get("lease_id") or "").strip(),
            "ephemeral": True,
            "loaded": True,
        }
        pending_skill_prompt = {
            "lease_id": public_result["lease_id"],
            "skill_id": public_result["skill_id"],
            "source_key": public_result["source_key"],
            "name": public_result["name"],
            "label": public_result["label"],
            "description": public_result["description"],
            "category": public_result["category"],
            "executor_type": public_result["executor_type"],
            "prompt": prompt_text,
        }
        return public_result, pending_skill_prompt

    @staticmethod
    def _prompt_only_skill_identity_key(skill_payload: dict[str, Any]) -> str:
        return str(
            skill_payload.get("skill_id")
            or skill_payload.get("source_key")
            or skill_payload.get("lease_id")
            or ""
        ).strip()

    @classmethod
    def _deduplicate_pending_skill_prompts(
        cls,
        pending_skill_prompts: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        if not isinstance(pending_skill_prompts, list):
            return []

        deduplicated: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for prompt_item in pending_skill_prompts:
            if not isinstance(prompt_item, dict):
                continue
            prompt_key = cls._prompt_only_skill_identity_key(prompt_item)
            if not prompt_key or prompt_key in seen_keys:
                continue
            prompt_text = str(prompt_item.get("prompt") or "").strip()
            if not prompt_text:
                continue
            deduplicated.append(prompt_item)
            seen_keys.add(prompt_key)
        return deduplicated

    @classmethod
    def _build_pending_skill_prompt_messages(
        cls,
        pending_skill_prompts: list[dict[str, Any]] | None,
    ) -> list[SystemMessage]:
        """把待注入的 prompt-only 技能全文合并成仅供当前轮次使用的系统消息。"""
        deduplicated = cls._deduplicate_pending_skill_prompts(pending_skill_prompts)
        if not deduplicated:
            return []

        sections: list[str] = [
            "## 按需加载的 Prompt-only Skills",
            "",
            "以下内容仅在当前轮次有效，当前轮次结束后会自动回收。不要把它当作长期上下文，也不要在后续轮次继续假设它仍然存在。",
            "",
        ]
        for prompt_item in deduplicated:
            title = str(prompt_item.get("label") or prompt_item.get("name") or prompt_item.get("source_key") or "Skill").strip()
            source_key = str(prompt_item.get("source_key") or "").strip()
            prompt_text = str(prompt_item.get("prompt") or "").strip()
            if not prompt_text:
                continue
            header = f"### {title}"
            if source_key:
                header += f" (`{source_key}`)"
            sections.extend([header, prompt_text, ""])

        content = "\n".join(sections).strip()
        if not content:
            return []
        return [SystemMessage(content=content)]

    @classmethod
    def _inject_pending_skill_prompts(
        cls,
        messages: list[Any],
        pending_skill_prompts: list[dict[str, Any]] | None,
    ) -> list[Any]:
        if not isinstance(messages, list):
            return []

        injected_messages = list(messages)
        prompt_messages = cls._build_pending_skill_prompt_messages(pending_skill_prompts)
        if not prompt_messages:
            return injected_messages

        insert_at = 0
        while insert_at < len(injected_messages) and isinstance(injected_messages[insert_at], SystemMessage):
            insert_at += 1

        for index, prompt_message in enumerate(prompt_messages):
            injected_messages.insert(insert_at + index, prompt_message)

        return injected_messages

    @staticmethod
    def _build_tool_not_found_result(tool_call_name: str, tools_by_name: dict[str, Any]) -> str:
        """把可用工具名回灌给模型，促使其基于真实列表重新选择。"""
        available_tool_names = list(tools_by_name.keys())
        preview_limit = 30
        preview = available_tool_names[:preview_limit]
        suffix = ""
        if len(available_tool_names) > preview_limit:
            suffix = f" 等共 {len(available_tool_names)} 个工具"
        available_text = ", ".join(preview) if preview else "无"
        return (
            f"工具未找到: {tool_call_name}。"
            f"请从当前可用工具列表中重新选择并调用: {available_text}{suffix}。"
        )

    def _resolve_tool(
        self,
        tool_call_name: str,
        tools_by_name: dict[str, Any],
        tools_by_alias: dict[str, Any],
    ) -> Any | None:
        """按精确名、别名顺序解析工具。"""
        tool_policy = getattr(self.agent_config, "tool_policy", None) or ToolPolicy()
        requested_name = tool_policy.resolve_tool_name(tool_call_name)

        candidates = (
            requested_name,
        )
        for candidate in candidates:
            if not candidate:
                continue
            tool = tools_by_name.get(candidate)
            if tool is not None:
                return tool

            tool = tools_by_alias.get(candidate)
            if tool is not None:
                return tool

        return None

    @staticmethod
    def _normalize_tool_alias(tool_name: str | None) -> str:
        if not tool_name:
            return ""

        normalized = str(tool_name).strip()
        if not normalized:
            return ""

        parts = normalized.split("__", 2)
        if len(parts) == 3:
            return parts[2]
        return normalized.replace("-", "_").replace(" ", "_")

    @classmethod
    def _tools_condition(cls, state: AgentState) -> Literal["tools", "__end__"]:
        """检测下一个节点是执行tools节点，还是直接结束"""
        # 1.提取状态中的最后一条消息(AI消息)
        messages = state["messages"]
        ai_message = messages[-1]

        # 2.检测是否存在tools_calls这个参数，如果存在则执行tools节点，否则结束
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"

        return END

    @classmethod
    def _preset_operation_condition(cls, state: AgentState) -> Literal["long_term_memory_recall", "__end__"]:
        """预设操作条件边，用于判断是否触发预设响应"""
        # 1.提取状态的最后一条消息
        message = state["messages"][-1]

        # 2.判断消息的类型，如果是AI消息则说明触发了审核机制，直接结束
        if message.type == "ai":
            return END

        return "long_term_memory_recall"

    def _calculate_usage(
        self,
        state: AgentState,
        gathered,
        *,
        messages: list[Any] | None = None,
    ) -> tuple[int, int, int, float, float, float, float]:
        """计算输入输出token以及价格"""
        encoding = tiktoken.get_encoding("cl100k_base")
        input_token_count = len(encoding.encode(normalize_usage_text(state["messages"])))
        output_token_count = len(encoding.encode(normalize_usage_text(gathered)))
        input_price, output_price, unit = self.llm.get_pricing()
        total_token_count = input_token_count + output_token_count
        total_price = (input_token_count * input_price + output_token_count * output_price) * unit
        return input_token_count, output_token_count, total_token_count, total_price, unit, input_price, output_price

    def _apply_output_review(self, content: str) -> str:
        """按输出审核规则处理文本"""
        review_config = self.agent_config.review_config
        if review_config["enable"] and review_config["outputs_config"]["enable"]:
            for keyword in review_config["keywords"]:
                content = re.sub(re.escape(keyword), "**", content, flags=re.IGNORECASE)
        return content

    @classmethod
    def _normalize_chunk_content(cls, content) -> str:
        """将chunk content规范化为文本"""
        if isinstance(content, str):
            return content
        return ""
