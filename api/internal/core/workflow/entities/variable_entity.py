import re
from enum import Enum
from typing import Union, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from internal.exception import ValidateErrorException


class VariableType(str, Enum):
    """变量的类型枚举"""
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOLEAN = "boolean"


# 变量类型与声明的映射
VARIABLE_TYPE_MAP = {
    VariableType.STRING.value: str,
    VariableType.INT.value: int,
    VariableType.FLOAT.value: float,
    VariableType.BOOLEAN.value: bool,
}

# 变量类型默认值映射
VARIABLE_TYPE_DEFAULT_VALUE_MAP = {
    VariableType.STRING.value: "",
    VariableType.INT.value: 0,
    VariableType.FLOAT.value: 0,
    VariableType.BOOLEAN.value: False,
}

# 变量名字正则匹配规则
VARIABLE_NAME_PATTERN = r'^[A-Za-z_][A-Za-z0-9_]*$'

# 描述最大长度
VARIABLE_DESCRIPTION_MAX_LENGTH = 1024


class VariableValueType(str, Enum):
    """变量内置值类型枚举"""
    REF = "ref"  # 引用类型
    LITERAL = "literal"  # 字面数据/直接输入
    GENERATED = "generated"  # 生成的值，一般用在开始节点或者output中


class VariableEntity(BaseModel):
    """变量实体信息"""

    class Value(BaseModel):
        """变量的实体值信息"""

        class Content(BaseModel):
            """变量内容实体信息，如果类型为引用，则使用content记录引用节点id+引用节点的变量名"""
            ref_node_id: Optional[UUID] = None
            ref_var_name: str = ""

            @field_validator("ref_node_id", mode="before")
            def validate_ref_node_id(cls, ref_node_id: Optional[UUID]):
                return ref_node_id if ref_node_id != "" else None

        type: VariableValueType = VariableValueType.LITERAL.value
        content: Union[Content, str, int, float, bool] = ""

    name: str = ""  # 变量的名字
    description: str = ""  # 变量的描述信息
    required: bool = True  # 变量是否必填
    type: VariableType = VariableType.STRING.value  # 变量的类型
    value: Value = Field(default_factory=lambda: {"type": VariableValueType.LITERAL.value, "content": ""})  # 变量对应的值
    meta: dict[str, Any] = Field(default_factory=dict)  # 变量元数据，存储一些额外的信息

    @field_validator("name")
    def validate_name(cls, value: str) -> str:
        """自定义校验函数，用于校验变量名字"""
        if not re.match(VARIABLE_NAME_PATTERN, value):
            raise ValidateErrorException("变量名字仅支持字母、数字和下划线，且以字母/下划线为开头")
        return value

    @field_validator("description")
    def validate_description(cls, value: str) -> str:
        """自定义校验函数，用于校验描述信息，截取前1024个字符"""
        return value[:VARIABLE_DESCRIPTION_MAX_LENGTH]