from pydantic import BaseModel,Field
from typing import Optional,Any
from enum import Enum

class ToolParamType(str,Enum):
    """工具参数类型枚举类"""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"

class ToolParams(BaseModel):
    """工具参数类型"""
    name: str # 参数的实际名字
    label: str # 参数的展示标签
    type: ToolParamType # 参数的类型
    required: bool = False # 是否必填
    default: Optional[Any] = None # 默认值
    min: Optional[float] = None # 最小值
    max: Optional[float] = None # 最大值
    options: list[dict[str,Any]] = Field(default_factory=list) # 下拉菜单选项列表


class ToolEntity(BaseModel):
    """工具实体类 存储的信息映射的是工具名.taml里的数据"""
    name: str # 工具名字
    label: str # 工具标签
    description: str # 工具描述
    params: list[ToolParams] = Field(default_factory=list) # 工具的参数信息
