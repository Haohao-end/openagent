from enum import Enum
from uuid import UUID
from typing import Any
from pydantic import BaseModel, Field, field_validator


class NodeType(str, Enum):
    """节点类型枚举"""
    START = "start"
    LLM = "llm"
    TOOL = "tool"
    CODE = "code"
    DATASET_RETRIEVAL = "dataset_retrieval"
    HTTP_REQUEST = "http_request"
    TEMPLATE_TRANSFORM = "template_transform"
    TEXT_PROCESSOR = "text_processor"
    VARIABLE_ASSIGNER = "variable_assigner"
    PARAMETER_EXTRACTOR = "parameter_extractor"
    IF_ELSE = "if_else"
    END = "end"


class BaseNodeData(BaseModel):
    """基础节点数据"""

    class Position(BaseModel):
        """节点坐标基础模型"""
        x: float = 0
        y: float = 0

    class ConfigDict:
        validate_by_name = True  # 允许通过字段名进行赋值

    id: UUID  # 节点id，数值必须唯一
    node_type: NodeType  # 节点类型
    title: str = ""  # 节点标题，数据也必须唯一
    description: str = ""  # 节点描述信息
    position: Position = Field(default_factory=lambda: {"x": 0, "y": 0})  # 节点对应的坐标信息

    @field_validator('node_type', mode='before')
    def convert_node_type(cls, v):
        if isinstance(v, NodeType):
            return v
        try:
            return NodeType(v)
        except ValueError:
            raise ValueError(f"Invalid node type: {v}")


class NodeStatus(str, Enum):
    """节点状态"""
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NodeResult(BaseModel):
    """节点运行结果"""
    node_data: BaseNodeData  # 节点基础数据
    status: NodeStatus = NodeStatus.RUNNING.value  # 节点运行状态
    inputs: dict[str, Any] = Field(default_factory=dict)  # 节点的输入数据
    outputs: dict[str, Any] = Field(default_factory=dict)  # 节点的输出数据
    latency: float = 0  # 节点响应耗时
    error: str = ""  # 节点运行错误信息
