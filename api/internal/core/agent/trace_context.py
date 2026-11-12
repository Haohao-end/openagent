"""Request-scoped LangChain trace delivery for Agent streams."""

from uuid import UUID, uuid4

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.workflow.debug_trace_callback import DebugTraceCallbackHandler


class AgentTraceContext:
    """Bind one bounded callback handler to one Agent task and queue manager."""

    def __init__(self, queue_manager, task_id: UUID | None = None):
        self.task_id = task_id if task_id is not None else uuid4()
        self._queue_manager = queue_manager
        defer_terminal = getattr(queue_manager, "defer_terminal", None)
        if callable(defer_terminal):
            defer_terminal(self.task_id)
        self.handler = DebugTraceCallbackHandler(event_sink=self._publish)

    @property
    def runnable_config(self) -> dict:
        """Return the LangChain callbacks for this request only."""
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
        """Stop callbacks from publishing after the response stream closes."""
        self.handler.close()
        cancel_task = getattr(self._queue_manager, "cancel_task", None)
        if callable(cancel_task):
            cancel_task(self.task_id)
