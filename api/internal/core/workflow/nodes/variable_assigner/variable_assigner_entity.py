from pydantic import Field, field_validator, model_validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import (
    VARIABLE_TYPE_DEFAULT_VALUE_MAP,
    VariableEntity,
    VariableValueType,
)
from internal.exception import ValidateErrorException


class VariableAssignerNodeData(BaseNodeData):
    """变量赋值节点数据"""

    inputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(
                name="value",
                type="string",
                value={"type": VariableValueType.LITERAL.value, "content": ""},
            )
        ]
    )
    outputs: list[VariableEntity] = Field(default_factory=list)

    @field_validator("inputs")
    def validate_inputs(cls, inputs: list[VariableEntity]) -> list[VariableEntity]:
        if len(inputs) <= 0:
            raise ValidateErrorException("变量赋值节点至少需要1个输入变量")

        input_names = [item.name for item in inputs]
        if len(input_names) != len(set(input_names)):
            raise ValidateErrorException("变量赋值节点输入变量名字不能重复")

        return inputs

    @model_validator(mode="after")
    def normalize_outputs(self):
        self.outputs = [
            VariableEntity(
                name=item.name,
                description=item.description,
                required=item.required,
                type=item.type,
                value={
                    "type": VariableValueType.GENERATED.value,
                    "content": VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(item.type),
                },
                meta=item.meta,
            )
            for item in self.inputs
        ]
        return self
