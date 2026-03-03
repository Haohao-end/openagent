import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from internal.exception import FailException
from .text_processor_entity import TextProcessorMode, TextProcessorNodeData


class TextProcessorNode(BaseNode):
    """文本处理节点"""

    node_data: TextProcessorNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        source_key = self.node_data.inputs[0].name
        source_text = str(inputs_dict.get(source_key, ""))

        if self.node_data.mode == TextProcessorMode.TRIM:
            output = source_text.strip()
        elif self.node_data.mode == TextProcessorMode.LOWER:
            output = source_text.lower()
        elif self.node_data.mode == TextProcessorMode.UPPER:
            output = source_text.upper()
        elif self.node_data.mode == TextProcessorMode.TITLE:
            output = source_text.title()
        else:
            raise FailException("文本处理节点处理模式出错")

        outputs = {"output": output, "length": len(output)}

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED.value,
                    inputs=inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }
