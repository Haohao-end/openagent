from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from internal.core.workflow.entities.node_entity import NodeType


class BaseEdgeData(BaseModel):
    """基础边数据"""
    id: UUID  # 边记录id
    source: UUID  # 边起点对应的节点id
    source_type: NodeType  # 边起点类型
    target: UUID  # 边目标对应的节点id
    target_type: NodeType  # 边目标类型
    source_handle: Optional[str] = None  # 源节点的连接点标识（用于条件分支：true/false）
    target_handle: Optional[str] = None  # 目标节点的连接点标识
