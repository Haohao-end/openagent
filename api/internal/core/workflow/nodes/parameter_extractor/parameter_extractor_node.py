import json
import re
import time
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.variable_entity import (
    VARIABLE_TYPE_DEFAULT_VALUE_MAP,
    VariableEntity,
    VariableType,
)
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from internal.exception import FailException
from .parameter_extractor_entity import ParameterExtractorMode, ParameterExtractorNodeData


class ParameterExtractorNode(BaseNode):
    """参数提取节点"""

    node_data: ParameterExtractorNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)
        source_key = self.node_data.inputs[0].name
        source_text = str(inputs_dict.get(source_key, ""))
        parsed_mapping = self._extract_mapping(source_text)

        outputs = {}
        for variable in self.node_data.outputs:
            raw_value = parsed_mapping.get(variable.name, None)
            if raw_value is None:
                if variable.required:
                    raise FailException(f"参数提取失败，缺少必填字段[{variable.name}]")
                outputs[variable.name] = VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(variable.type)
                continue

            try:
                outputs[variable.name] = self._cast_variable_value(raw_value, variable)
            except Exception:
                if variable.required:
                    raise FailException(f"参数提取失败，字段[{variable.name}]类型转换出错")
                outputs[variable.name] = VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(variable.type)

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

    def _extract_mapping(self, source_text: str) -> dict[str, Any]:
        mode = self.node_data.mode
        mapping = {}

        if mode in (ParameterExtractorMode.AUTO, ParameterExtractorMode.JSON):
            mapping = self._try_parse_json(source_text)
            if mapping:
                return mapping
            if mode == ParameterExtractorMode.JSON:
                raise FailException("参数提取失败，输入内容不是有效的JSON对象")

        if mode in (ParameterExtractorMode.AUTO, ParameterExtractorMode.KV):
            return self._parse_key_value(source_text)

        return mapping

    @staticmethod
    def _try_parse_json(source_text: str) -> dict[str, Any]:
        try:
            data = json.loads(source_text)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _parse_key_value(source_text: str) -> dict[str, Any]:
        mapping = {}
        segments = re.split(r"[&\n;,]+", source_text)
        for segment in segments:
            content = segment.strip()
            if not content:
                continue

            if "=" in content:
                key, value = content.split("=", 1)
            elif ":" in content:
                key, value = content.split(":", 1)
            else:
                continue

            mapping[key.strip()] = value.strip().strip('"').strip("'")

        return mapping

    @staticmethod
    def _cast_variable_value(raw_value: Any, variable: VariableEntity) -> Any:
        if variable.type == VariableType.STRING.value:
            return str(raw_value)
        if variable.type == VariableType.INT.value:
            return int(raw_value)
        if variable.type == VariableType.FLOAT.value:
            return float(raw_value)
        if variable.type == VariableType.BOOLEAN.value:
            if isinstance(raw_value, bool):
                return raw_value
            if isinstance(raw_value, str):
                normalized = raw_value.strip().lower()
                if normalized in {"true", "1", "yes", "y", "on"}:
                    return True
                if normalized in {"false", "0", "no", "n", "off"}:
                    return False
            if isinstance(raw_value, (int, float)):
                return bool(raw_value)
            raise ValueError("invalid boolean value")

        return raw_value
