from enum import Enum

from pydantic import Field, field_validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import (
    VARIABLE_TYPE_DEFAULT_VALUE_MAP,
    VariableEntity,
    VariableType,
    VariableValueType,
)
from internal.exception import ValidateErrorException


class ParameterExtractorMode(str, Enum):
    """参数提取模式"""

    AUTO = "auto"
    JSON = "json"
    KV = "kv"


class ParameterExtractorNodeData(BaseNodeData):
    """参数提取节点数据"""

    mode: ParameterExtractorMode = ParameterExtractorMode.AUTO
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
                name="param",
                type=VariableType.STRING.value,
                value={"type": VariableValueType.GENERATED.value, "content": ""},
            )
        ]
    )

    @field_validator("inputs")
    def validate_inputs(cls, inputs: list[VariableEntity]) -> list[VariableEntity]:
        if len(inputs) <= 0:
            raise ValidateErrorException("参数提取节点至少需要1个输入变量")

        if inputs[0].type != VariableType.STRING.value:
            raise ValidateErrorException("参数提取节点输入变量类型仅支持STRING")

        return inputs

    @field_validator("outputs", mode="before")
    def validate_outputs(cls, outputs: list[VariableEntity]) -> list[VariableEntity]:
        if not outputs or len(outputs) <= 0:
            raise ValidateErrorException("参数提取节点至少需要1个输出变量")

        output_entities: list[VariableEntity] = []
        for output in outputs:
            output_entity = output if isinstance(output, VariableEntity) else VariableEntity(**output)
            output_entities.append(
                VariableEntity(
                    name=output_entity.name,
                    description=output_entity.description,
                    required=output_entity.required,
                    type=output_entity.type,
                    value={
                        "type": VariableValueType.GENERATED.value,
                        "content": VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(output_entity.type),
                    },
                    meta=output_entity.meta,
                )
            )

        output_names = [item.name for item in output_entities]
        if len(output_names) != len(set(output_names)):
            raise ValidateErrorException("参数提取节点输出变量名字不能重复")

        return output_entities
