"""A2ADeepThinkingAgent - 保留 A2A 输出语义的深度思考智能体。"""
import json
import logging
import time
import uuid

from langchain_core.messages import AIMessage, messages_to_dict

from internal.core.agent.entities.agent_entity import AgentState, MAX_ITERATION_RESPONSE
from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature

from .deep_thinking_agent import DeepThinkingAgent


class A2ADeepThinkingAgent(DeepThinkingAgent):
    """面向 A2A 场景的深度思考智能体。

    复用 DeepThinkingAgent 的 deep_route / sandbox / timeline / artifact 能力，
    仅将最终 LLM 输出节点替换为 A2A 的缓冲发布语义，避免工具调用前的过渡话术
    直接暴露给用户。
    """

    name: str = "a2a_deep_thinking_agent"

    def _llm_node(self, state: AgentState) -> AgentState:
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
                ),
            )
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END.value,
                ),
            )
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
            logging.exception("A2A 深度思考 LLM 节点发生错误: %s", e)
            self.agent_queue_manager.publish_failure(
                state["task_id"],
                e,
                context="LLM节点发生错误",
            )
            raise

        if gathered is None:
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(id=uuid.uuid4(), task_id=state["task_id"], event=QueueEvent.AGENT_END.value),
            )
            return {
                "messages": [AIMessage(content="")],
                "iteration_count": state["iteration_count"] + 1,
            }

        (
            input_token_count,
            output_token_count,
            total_token_count,
            total_price,
            unit,
            input_price,
            output_price,
        ) = self._calculate_usage(state, gathered)
        final_tool_calls = getattr(gathered, "tool_calls", []) or []
        if saw_tool_calls or final_tool_calls:
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
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
                ),
            )
            return {
                "messages": [gathered],
                "iteration_count": state["iteration_count"] + 1,
            }

        for chunk_content in buffered_text_chunks:
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=event_id,
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_MESSAGE.value,
                    thought=chunk_content,
                    message=messages_to_dict(state["messages"]),
                    answer=chunk_content,
                    latency=(time.perf_counter() - start_at),
                ),
            )

        if buffered_text_chunks:
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
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
                ),
            )
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END.value,
                ),
            )
        else:
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(id=uuid.uuid4(), task_id=state["task_id"], event=QueueEvent.AGENT_END.value),
            )

        return {"messages": [gathered], "iteration_count": state["iteration_count"] + 1}
