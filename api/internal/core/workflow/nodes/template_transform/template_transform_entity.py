from pydantic import Field, field_validator
from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType


class TemplateTransformNodeData(BaseNodeData):
    """模板转换节点数据"""
    template: str = ""  # 需要拼接转换的字符串模板
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入列表信息
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="output", value={"type": VariableValueType.GENERATED.value})
        ]
    )

    @field_validator("outputs", mode="before")
    def validate_outputs(cls, outputs: list[VariableEntity]) -> list[VariableEntity]:
        return [
            VariableEntity(name="output", value={"type": VariableValueType.GENERATED.value})
        ]