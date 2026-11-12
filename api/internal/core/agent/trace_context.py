"""Request-scoped LangChain trace delivery for Agent streams."""

from uuid import UUID, uuid4

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.workflow.debug_trace_callback import DebugTraceCallbackHandler


class AgentTraceContext:
    """Bind one bounded callback handler to one Agent task and queue manager."""

    def __init__(self, queue_manager, task_id: UUID | None = None):
        self.task_id = task_id or uuid4()
        self._queue_manager = queue_manager
        self.handler = DebugTraceCallbackHandler(event_sink=self._publish)

    @property
    def runnable_config(self) -> dict:
        return {"callbacks": [self.handler]}

    def _publish(self, serialized_event: str) -> None:
        self._queue_manager.publish(
            self.task_id,
            AgentThought(
                id=uuid4(),
                task_id=self.task_id,
                event=QueueEvent.CALLABLE_TRACE,
                observation=serialized_event,
            ),
        )

    def close(self) -> None:
        """Stop late callbacks when this response stream is closed."""
        self.handler.close()
