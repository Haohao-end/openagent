from enum import Enum

from pydantic import Field, field_validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import (
    VariableEntity,
    VariableType,
    VariableValueType,
)
from internal.exception import ValidateErrorException


class TextProcessorMode(str, Enum):
    """文本处理模式"""

    TRIM = "trim"
    LOWER = "lower"
    UPPER = "upper"
    TITLE = "title"


class TextProcessorNodeData(BaseNodeData):
    """文本处理节点数据"""

    mode: TextProcessorMode = TextProcessorMode.TRIM
    inputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(
                name="text",
                type=VariableType.STRING.value,
                value={"type": VariableValueType.LITERAL.value, "content": ""},
            )
        ]
    )
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(
                name="output",
                type=VariableType.STRING.value,
                value={"type": VariableValueType.GENERATED.value, "content": ""},
            ),
            VariableEntity(
                name="length",
                type=VariableType.INT.value,
                value={"type": VariableValueType.GENERATED.value, "content": 0},
            ),
        ]
    )

    @field_validator("inputs")
    def validate_inputs(cls, inputs: list[VariableEntity]) -> list[VariableEntity]:
        if len(inputs) <= 0:
            raise ValidateErrorException("文本处理节点至少需要1个输入变量")

        if inputs[0].type != VariableType.STRING.value:
            raise ValidateErrorException("文本处理节点输入变量类型仅支持STRING")

        return inputs

    @field_validator("outputs", mode="before")
    def validate_outputs(cls, _outputs: list[VariableEntity]) -> list[VariableEntity]:
        return [
            VariableEntity(
                name="output",
                type=VariableType.STRING.value,
                value={"type": VariableValueType.GENERATED.value, "content": ""},
            ),
            VariableEntity(
                name="length",
                type=VariableType.INT.value,
                value={"type": VariableValueType.GENERATED.value, "content": 0},
            ),
        ]
