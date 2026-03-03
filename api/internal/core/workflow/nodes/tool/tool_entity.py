from typing import Any, Literal
from pydantic import Field, field_validator
from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity

class ToolNodeData(BaseNodeData):
    """工具节点数据"""
    node_type: Literal["tool"] = "tool"  # 明确指定节点类型
    tool_type: Literal["builtin_tool", "api_tool", ""] = Field(default="", alias="type")
    provider_id: str = ""
    tool_id: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    inputs: list[VariableEntity] = Field(default_factory=list)
    outputs: list[VariableEntity] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)  # 添加meta字段

    model_config = {
        "populate_by_name": True
    }

    @field_validator("outputs", mode="before")
    def validate_outputs(cls, outputs: list[VariableEntity]):
        # 处理各种可能的输入情况
        if outputs is None:
            return [VariableEntity(name="text", type="string", value={"type": "generated"})]
        if isinstance(outputs, list):
            if not outputs:
                return [VariableEntity(name="text", type="string", value={"type": "generated"})]
            return outputs
        return [VariableEntity(name="text", type="string", value={"type": "generated"})]