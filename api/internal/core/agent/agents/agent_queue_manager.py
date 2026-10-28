import queue
import os
import threading
import time
import uuid
from queue import Queue
from typing import Generator
from uuid import UUID
from redis import Redis
from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.agent.failure_utils import build_failure_observation, classify_failure_event
from internal.entity.conversation_entity import InvokeFrom


class AgentQueueManager:
    """智能体队列管理器"""
    user_id: UUID
    invoke_from: InvokeFrom
    redis_client: Redis
    _queues: dict[str, Queue]
    _terminal_events: dict[str, set[str]]
    _DEFAULT_LISTEN_TIMEOUT_SECONDS: int = 1800

    def __init__(
            self,
            user_id: UUID,
            invoke_from: InvokeFrom,
    ) -> None:
        """构造函数，初始化智能体队列管理器"""
        # 1.初始化数据
        self.user_id = user_id
        self.invoke_from = invoke_from
        self._queues = {}
        self._terminal_events = {}
        self._queue_lock = threading.Lock()

        # 2.内部初始化redis_client
        from app.http.module import injector
        self.redis_client = injector.get(Redis)

    def listen(self, task_id: UUID) -> Generator:
        """监听队列返回的生成式数据"""
        # 1.定义基础数据记录超时时间、开始时间、最后一次ping通时间
        listen_timeout = self._read_listen_timeout_seconds()
        start_time = time.time()
        last_ping_time = 0

        # 2.创建循环队列执行死循环读取数据，直到超时或者数据读取完毕
        while True:
            try:
                # 3.从队列中提取数据并检测数据是否存在，如果存在则使用yield关键字返回 item为agent_thought
                item = self.queue(task_id).get(timeout=1)
                if item is None:
                    break
                yield item
            except queue.Empty:
                continue
            finally:
                # 4.计算获取数据的总耗时
                elapsed_time = time.time() - start_time

                # 5.每10秒发起一个ping请求
                if elapsed_time // 10 > last_ping_time:
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.PING.value,
                    ))
                    last_ping_time = elapsed_time // 10

                # 6.判断总耗时是否超时，如果超时则往队列中添加超时事件
                if elapsed_time >= listen_timeout:
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.TIMEOUT.value,
                    ))

                # 7.检测是否停止，如果已经停止则添加停止事件
                if self._is_stopped(task_id):
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.STOP.value,
                    ))

    @classmethod
    def _read_listen_timeout_seconds(cls) -> int:
        """读取监听超时时间，默认放宽到长任务可完成的范围。"""
        raw_value = str(os.getenv("AGENT_LISTEN_TIMEOUT_SECONDS", "")).strip()
        if not raw_value:
            return cls._DEFAULT_LISTEN_TIMEOUT_SECONDS

        try:
            parsed_value = int(raw_value)
        except ValueError:
            return cls._DEFAULT_LISTEN_TIMEOUT_SECONDS

        return parsed_value if parsed_value > 0 else cls._DEFAULT_LISTEN_TIMEOUT_SECONDS

    def stop_listen(self, task_id: UUID) -> None:
        """停止监听队列信息"""
        self.queue(task_id).put(None)

    def publish_error(self, task_id: UUID, error) -> None:
        """发布错误信息到队列"""
        if isinstance(error, BaseException):
            self.publish_failure(task_id, error)
            return

        self.publish(task_id, AgentThought(
            id=uuid.uuid4(),
            task_id=task_id,
            event=QueueEvent.ERROR.value,
            observation=str(error),
        ))

    def publish_failure(self, task_id: UUID, error, context: str = "") -> None:
        """发布已归类的异常终态事件。"""
        failure_event = classify_failure_event(error)
        observation = build_failure_observation(error, context)
        self.publish(task_id, AgentThought(
            id=uuid.uuid4(),
            task_id=task_id,
            event=failure_event.value,
            observation=observation,
        ))

    def _is_stopped(self, task_id: UUID) -> bool:
        """检测任务是否停止"""
        task_stopped_cache_key = self.generate_task_stopped_cache_key(task_id)
        result = self.redis_client.get(task_stopped_cache_key)

        if result is not None:
            return True
        return False

    def publish(self, task_id: UUID, agent_thought: AgentThought) -> None:
        """发布事件信息到队列"""
        event_value = str(getattr(agent_thought.event, "value", agent_thought.event) or "")
        terminal_events = {
            QueueEvent.STOP.value,
            QueueEvent.ERROR.value,
            QueueEvent.TIMEOUT.value,
            QueueEvent.AGENT_END.value,
        }
        if self._terminal_events.get(str(task_id)):
            if event_value not in self._terminal_events.get(str(task_id), set()):
                return
        if event_value in terminal_events:
            task_terminal_events = self._terminal_events.setdefault(str(task_id), set())
            if event_value in task_terminal_events:
                return
            task_terminal_events.add(event_value)

        # 1.将事件添加到队列中
        self.queue(task_id).put(agent_thought)

        # 2.检测事件类型是否为需要停止的类型，涵盖STOP、ERROR、TIMEOUT、AGENT_END
        if event_value in terminal_events:
            self.stop_listen(task_id)

    def queue(self, task_id: UUID) -> Queue:
        """根据传递的task_id获取对应的任务队列信息"""
        task_key = str(task_id)
        with self._queue_lock:
            q = self._queues.get(task_key)
            if q is None:
                user_prefix = "account" if self.invoke_from in [
                    InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER, InvokeFrom.ASSISTANT_AGENT
                ] else "end-user"
                self.redis_client.setex(
                    self.generate_task_belong_cache_key(task_id),
                    1800,
                    f"{user_prefix}-{self.user_id}",
                )
                q = self._queues[task_key] = Queue()

        return q

    @classmethod
    def set_stop_flag(cls, task_id: UUID, invoke_from: InvokeFrom, user_id: UUID) -> None:
        """根据传递的任务id+调用来源停止某次会话"""
        # 1.获取redis_client客户端
        from app.http.module import injector
        redis_client = injector.get(Redis)

        # 2.获取当前任务的缓存键，如果任务没执行，则不需要停止
        result = redis_client.get(cls.generate_task_belong_cache_key(task_id))
        if not result:
            return

        # 3.计算对应缓存键的结果
        user_prefix = "account" if invoke_from in [
            InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER, InvokeFrom.ASSISTANT_AGENT
        ] else "end-user"
        if result.decode("utf-8") != f"{user_prefix}-{str(user_id)}":
            return

        # 4.生成停止键标识
        stopped_cache_key = cls.generate_task_stopped_cache_key(task_id)
        redis_client.setex(stopped_cache_key, 600, 1)

    @classmethod
    def generate_task_belong_cache_key(cls, task_id: UUID) -> str:
        """生成任务专属的缓存键"""
        return f"generate_task_belong:{str(task_id)}"

    @classmethod
    def generate_task_stopped_cache_key(cls, task_id: UUID) -> str:
        """生成任务已停止的缓存键"""
        return f"generate_task_stopped:{str(task_id)}"
