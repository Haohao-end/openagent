import uuid
from abc import abstractmethod
from contextlib import nullcontext
import logging
from threading import Event, Thread
from typing import Optional, Any, Iterator
from flask import has_app_context
from internal.core.language_model.entities.model_entity import BaseLanguageModel
from langchain_core.load import Serializable
from pydantic import ConfigDict, PrivateAttr
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from internal.core.agent.entities.agent_entity import AgentConfig, AgentState
from internal.core.agent.entities.queue_entity import AgentResult, AgentThought, QueueEvent
from internal.core.agent.usage_utils import summarize_agent_thoughts
from internal.exception import FailException
from .agent_queue_manager import AgentQueueManager


class AgentStreamCancelled(Exception):
    """用于停止尚未开始的工具调用，而不把客户端断流记录为执行失败。"""


class BaseAgent(Serializable, Runnable):
    """基于Runnable的基础智能体基类"""
    name: str = "default_agent"  # 添加默认名称
    llm: BaseLanguageModel
    agent_config: AgentConfig
    _agent: CompiledStateGraph = PrivateAttr(None)
    _agent_queue_manager: AgentQueueManager = PrivateAttr(None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(
            self,
            llm: BaseLanguageModel,
            agent_config: AgentConfig,
            *args,
            **kwargs,
    ):
        """构造函数，初始化智能体图结构程序"""
        super().__init__(*args, llm=llm, agent_config=agent_config, **kwargs)
        self._agent = self._build_agent()
        self._agent_queue_manager = AgentQueueManager(
            user_id=agent_config.user_id,
            invoke_from=agent_config.invoke_from,
        )

    @abstractmethod
    def _build_agent(self) -> CompiledStateGraph:
        """构建智能体函数，等待子类实现"""
        raise NotImplementedError("_build_agent()未实现")

    def invoke(self, input: AgentState, config: Optional[RunnableConfig] = None) -> AgentResult:
        """块内容响应，一次性生成完整内容后返回"""
        # 1.调用stream方法获取流式事件输出数据
        content = input["messages"][0].content
        query = ""
        image_urls = []
        if isinstance(content, str):
            query = content
        elif isinstance(content, list):
            query = next((chunk.get("text", "") for chunk in content if chunk.get("type") == "text"), "")
            image_urls = [chunk["image_url"]["url"] for chunk in content if chunk.get("type") == "image_url"]
        agent_result = AgentResult(query=query, image_urls=image_urls)
        agent_thoughts = {}
        for agent_thought in self.stream(input, config):
            # 2.提取事件id并转换成字符串
            event_id = str(agent_thought.id)

            # 3.除了ping事件，其他事件全部记录
            if agent_thought.event != QueueEvent.PING:
                # 4.单独处理agent_message事件，因为该事件为数据叠加
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    # 5.检测是否已存储了事件
                    if event_id not in agent_thoughts:
                        # 6.初始化智能体消息事件
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 7.叠加智能体消息事件
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "latency": agent_thought.latency,
                        })
                    # 8.更新智能体消息答案
                    agent_result.answer += agent_thought.answer
                else:
                    # 9.处理其他类型的智能体事件，类型均为覆盖
                    agent_thoughts[event_id] = agent_thought

                    # 10.单独判断是否为异常消息类型，如果是则修改状态并记录错误
                    if agent_thought.event in [QueueEvent.STOP, QueueEvent.TIMEOUT, QueueEvent.ERROR]:
                        agent_result.status = agent_thought.event
                        agent_result.error = agent_thought.observation if agent_thought.event == QueueEvent.ERROR else ""

        # 11.将推理字典转换成列表并存储
        agent_result.agent_thoughts = [agent_thought for agent_thought in agent_thoughts.values()]

        # 12.完善message
        agent_result.message = next(
            (agent_thought.message for agent_thought in agent_thoughts.values()
             if agent_thought.event == QueueEvent.AGENT_MESSAGE),
            []
        )

        # 13.更新消息级统计
        usage_summary = summarize_agent_thoughts(agent_thoughts.values())
        agent_result.total_token_count = usage_summary.total_token_count
        agent_result.total_price = usage_summary.total_price
        agent_result.latency = usage_summary.latency

        return agent_result

    def stream(
            self,
            input: AgentState,
            config: Optional[RunnableConfig] = None,
            **kwargs: Optional[Any],
    ) -> Iterator[AgentThought]:
        """流式输出，每个Not节点或者LLM每生成一个token时则会返回相应内容"""
        # 1.检测子类是否已构建Agent智能体，如果未构建则抛出错误
        if not self._agent:
            raise FailException("智能体未成功构建，请核实后尝试")

        # 2.构建对应的任务id及数据初始化
        input["task_id"] = input.get("task_id", uuid.uuid4())
        input["history"] = input.get("history", [])
        input["iteration_count"] = input.get("iteration_count", 0)
        input["pending_skill_prompts"] = input.get("pending_skill_prompts", [])
        cancel_event = Event()
        input["cancel_event"] = cancel_event

        # 3.创建子线程并执行；子线程不会继承 Flask app context，因此需要在运行时显式补上下文
        runtime_flask_app = getattr(self.agent_config, "runtime_flask_app", None)

        def _invoke_agent() -> None:
            app_context = nullcontext()
            if runtime_flask_app is not None and not has_app_context():
                app_context = runtime_flask_app.app_context()
            with app_context:
                try:
                    self._agent.invoke(input, config=config)
                except AgentStreamCancelled:
                    return
                except Exception as error:
                    if cancel_event.is_set():
                        return
                    logging.exception("智能体执行线程发生异常: %s", error)
                    self._agent_queue_manager.publish_failure(
                        input["task_id"],
                        error,
                        context="智能体执行异常",
                    )

        thread = Thread(target=_invoke_agent)
        thread.start()

        # 4.调用队列管理器监听数据并返回迭代器
        try:
            yield from self._agent_queue_manager.listen(input["task_id"])
        finally:
            cancel_event.set()
            is_alive = getattr(thread, "is_alive", None)
            if callable(is_alive) and is_alive():
                join = getattr(thread, "join", None)
                if callable(join):
                    join(timeout=1)

    @property
    def agent_queue_manager(self) -> AgentQueueManager:
        """只读属性，返回智能体队列管理器"""
        return self._agent_queue_manager
