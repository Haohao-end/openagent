from enum import Enum
from pydantic import BaseModel, Field
from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity


class ConditionOperator(str, Enum):
    """条件运算符枚举"""
    EQUALS = "equals"  # 等于
    NOT_EQUALS = "not_equals"  # 不等于
    CONTAINS = "contains"  # 包含
    NOT_CONTAINS = "not_contains"  # 不包含
    STARTS_WITH = "starts_with"  # 以...开始
    ENDS_WITH = "ends_with"  # 以...结束
    IS_EMPTY = "is_empty"  # 为空
    IS_NOT_EMPTY = "is_not_empty"  # 不为空
    GREATER_THAN = "greater_than"  # 大于
    LESS_THAN = "less_than"  # 小于
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"  # 大于等于
    LESS_THAN_OR_EQUAL = "less_than_or_equal"  # 小于等于


class LogicalOperator(str, Enum):
    """逻辑运算符枚举"""
    AND = "and"  # 与
    OR = "or"  # 或


class Condition(BaseModel):
    """单个条件配置"""
    variable_name: str = ""  # 变量名
    operator: ConditionOperator = ConditionOperator.EQUALS  # 运算符
    compare_value: str = ""  # 比较值


class IfElseNodeData(BaseNodeData):
    """条件分支节点数据"""
    conditions: list[Condition] = Field(default_factory=list)  # 条件列表
    logical_operator: LogicalOperator = LogicalOperator.AND  # 多条件之间的逻辑关系
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量列表
    outputs: list[VariableEntity] = Field(default_factory=list)  # 输出变量列表（用于传递数据）
