import json
import logging
import re
import time
import uuid
from typing import Literal

import tiktoken
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.messages import messages_to_dict
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from internal.core.agent.entities.agent_entity import (
    AGENT_SYSTEM_PROMPT_TEMPLATE,
    DATASET_RETRIEVAL_TOOL_NAME,
    MAX_ITERATION_RESPONSE,
    AgentState,
)
from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.exception import FailException

from .base_agent import BaseAgent


class A2AFunctionCallAgent(BaseAgent):
    """面向A2A委派场景的函数调用Agent。

    与通用 FunctionCallAgent 的差异在于：
    - 工具调用轮先完整缓冲 LLM 输出；
    - 只有确认本轮不存在 tool_calls 时，才发布 AGENT_MESSAGE；
    - 避免模型在触发工具前输出的过渡话术直接暴露给用户。
    """

    def _build_agent(self) -> CompiledStateGraph:
        """构建LangGraph图结构编译程序。"""
        graph = StateGraph(AgentState)
        graph.add_node("preset_operation", self._preset_operation_node)
        graph.add_node("long_term_memory_recall", self._long_term_memory_recall_node)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tools", self._tools_node)

        graph.set_entry_point("preset_operation")
        graph.add_conditional_edges("preset_operation", self._preset_operation_condition)
        graph.add_edge("long_term_memory_recall", "llm")
        graph.add_conditional_edges("llm", self._tools_condition)
        graph.add_edge("tools", "llm")

        return graph.compile()

    def _preset_operation_node(self, state: AgentState) -> AgentState:
        """预设操作，涵盖：输入审核、数据预处理、条件边等。"""
        review_config = self.agent_config.review_config
        query = state["messages"][-1].content

        if review_config["enable"] and review_config["inputs_config"]["enable"]:
            contains_keyword = any(keyword in query for keyword in review_config["keywords"])
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
        """长期记忆召回节点。"""
        long_term_memory = ""
        if self.agent_config.enable_long_term_memory:
            long_term_memory = state["long_term_memory"]
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.LONG_TERM_MEMORY_RECALL.value,
                observation=long_term_memory,
            ))

        preset_messages = [
            SystemMessage(AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                preset_prompt=self.agent_config.preset_prompt,
                long_term_memory=long_term_memory,
            ))
        ]

        history = state["history"]
        if isinstance(history, list) and len(history) > 0:
            if len(history) % 2 != 0:
                self.agent_queue_manager.publish_error(state["task_id"], "智能体历史消息列表格式错误")
                logging.exception(
                    "智能体历史消息列表格式错误, len(history)=%s, history=%s",
                    len(history),
                    json.dumps(messages_to_dict(history)),
                )
                raise FailException("智能体历史消息列表格式错误")
            preset_messages.extend(history)

        human_message = state["messages"][-1]
        preset_messages.append(HumanMessage(human_message.content))
        return {
            "messages": [RemoveMessage(id=human_message.id), *preset_messages],
        }

    def _llm_node(self, state: AgentState) -> AgentState:
        """大语言模型节点。

        A2A 场景下先缓冲本轮输出，只有确认没有 tool_calls 时才向用户侧发布消息。
        """
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
            return {"messages": [AIMessage(MAX_ITERATION_RESPONSE)]}

        event_id = uuid.uuid4()
        start_at = time.perf_counter()
        llm = self.llm
        if (
            ModelFeature.TOOL_CALL.value in llm.features
            and hasattr(llm, "bind_tools")
            and callable(getattr(llm, "bind_tools"))
            and len(self.agent_config.tools) > 0
        ):
            llm = llm.bind_tools(self.agent_config.tools)

        gathered = None
        saw_tool_calls = False
        buffered_text_chunks: list[str] = []
        try:
            for chunk in llm.stream(state["messages"]):
                if chunk is None:
                    continue
                if gathered is None:
                    gathered = chunk
                else:
                    gathered += chunk
                    if gathered is None:
                        gathered = chunk

                if getattr(chunk, "tool_calls", None):
                    saw_tool_calls = True

                content = self._normalize_chunk_content(getattr(chunk, "content", ""))
                if content:
                    buffered_text_chunks.append(self._apply_output_review(content))
        except Exception as e:
            logging.exception(f"LLM节点发生错误, 错误信息: {str(e)}")
            self.agent_queue_manager.publish_error(state["task_id"], f"LLM节点发生错误, 错误信息: {str(e)}")
            raise e

        if gathered is None:
            return {
                "messages": [AIMessage(content="")],
                "iteration_count": state["iteration_count"] + 1,
            }

        input_token_count, output_token_count, total_token_count, total_price, unit, input_price, output_price = (
            self._calculate_usage(state, gathered)
        )
        final_tool_calls = getattr(gathered, "tool_calls", []) or []
        if saw_tool_calls or final_tool_calls:
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=event_id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_THOUGHT.value,
                thought=json.dumps(final_tool_calls),
                message=messages_to_dict(state["messages"]),
                message_token_count=input_token_count,
                message_unit_price=input_price,
                message_price_unit=unit,
                answer="",
                answer_token_count=output_token_count,
                answer_unit_price=output_price,
                answer_price_unit=unit,
                total_token_count=total_token_count,
                total_price=total_price,
                latency=(time.perf_counter() - start_at),
            ))
            return {"messages": [gathered], "iteration_count": state["iteration_count"] + 1}

        for chunk_content in buffered_text_chunks:
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=event_id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_MESSAGE.value,
                thought=chunk_content,
                message=messages_to_dict(state["messages"]),
                answer=chunk_content,
                latency=(time.perf_counter() - start_at),
            ))

        if buffered_text_chunks:
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=event_id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_MESSAGE.value,
                thought="",
                message=messages_to_dict(state["messages"]),
                message_token_count=input_token_count,
                message_unit_price=input_price,
                message_price_unit=unit,
                answer="",
                answer_token_count=output_token_count,
                answer_unit_price=output_price,
                answer_price_unit=unit,
                total_token_count=total_token_count,
                total_price=total_price,
                latency=(time.perf_counter() - start_at),
            ))
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.AGENT_END.value,
            ))

        return {"messages": [gathered], "iteration_count": state["iteration_count"] + 1}

    def _tools_node(self, state: AgentState) -> AgentState:
        """工具执行节点。"""
        tools_by_name = {tool.name: tool for tool in self.agent_config.tools}
        tool_calls = state["messages"][-1].tool_calls

        messages = []
        for tool_call in tool_calls:
            event_id = uuid.uuid4()
            start_at = time.perf_counter()

            try:
                tool = tools_by_name[tool_call["name"]]
                tool_result = tool.invoke(tool_call["args"])
            except Exception as e:
                tool_result = f"工具执行出错: {str(e)}"

            messages.append(ToolMessage(
                tool_call_id=tool_call["id"],
                content=json.dumps(tool_result),
                name=tool_call["name"],
            ))

            event = (
                QueueEvent.AGENT_ACTION.value
                if tool_call["name"] != DATASET_RETRIEVAL_TOOL_NAME
                else QueueEvent.DATASET_RETRIEVAL.value
            )
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=event_id,
                task_id=state["task_id"],
                event=event,
                observation=json.dumps(tool_result),
                tool=tool_call["name"],
                tool_input=tool_call["args"],
                latency=(time.perf_counter() - start_at),
            ))

        return {"messages": messages}

    @classmethod
    def _tools_condition(cls, state: AgentState) -> Literal["tools", "__end__"]:
        """检测下一个节点是执行tools节点，还是直接结束。"""
        ai_message = state["messages"][-1]
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"
        return END

    @classmethod
    def _preset_operation_condition(cls, state: AgentState) -> Literal["long_term_memory_recall", "__end__"]:
        """预设操作条件边，用于判断是否触发预设响应。"""
        message = state["messages"][-1]
        if message.type == "ai":
            return END
        return "long_term_memory_recall"

    def _calculate_usage(self, state: AgentState, gathered) -> tuple[int, int, int, float, float, float, float]:
        """计算输入输出token以及价格。"""
        encoding = tiktoken.get_encoding("cl100k_base")
        input_token_count = len(encoding.encode(str(state["messages"])))
        output_token_count = len(encoding.encode(str(gathered)))
        input_price, output_price, unit = self.llm.get_pricing()
        total_token_count = input_token_count + output_token_count
        total_price = (input_token_count * input_price + output_token_count * output_price) * unit
        return input_token_count, output_token_count, total_token_count, total_price, unit, input_price, output_price

    def _apply_output_review(self, content: str) -> str:
        """按输出审核规则处理文本。"""
        review_config = self.agent_config.review_config
        if review_config["enable"] and review_config["outputs_config"]["enable"]:
            for keyword in review_config["keywords"]:
                content = re.sub(re.escape(keyword), "**", content, flags=re.IGNORECASE)
        return content

    @classmethod
    def _normalize_chunk_content(cls, content) -> str:
        """将 chunk content 规范化为文本。"""
        if isinstance(content, str):
            return content
        return ""
