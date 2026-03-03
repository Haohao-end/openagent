from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field
from internal.entity.conversation_entity import MessageStatus

class QueueEvent(str, Enum):
    """队列事件枚举类型"""
    LONG_TERM_MEMORY_RECALL = "long_term_memory_recall"  # 长期记忆召回事件
    AGENT_THOUGHT = "agent_thought"  # 智能体观察事件
    AGENT_MESSAGE = "agent_message"  # 智能体消息事件
    AGENT_ACTION = "agent_action"  # 智能体动作
    DATASET_RETRIEVAL = "dataset_retrieval"  # 知识库检索事件
    AGENT_END = "agent_end"  # 智能体结束事件
    STOP = "stop"  # 智能体停止事件
    ERROR = "error"  # 智能体错误事件
    TIMEOUT = "timeout"  # 智能体超时事件
    PING = "ping"  # ping联通事件


class AgentThought(BaseModel):
    """智能体推理观察输出内容"""
    id: UUID  # 事件对应的id，同一个事件的id是一样的
    task_id: UUID  # 任务id

    # 事件的推理与观察
    event: QueueEvent
    thought: str = ""  # LLM推理内容
    observation: str = ""  # 观察内容

    # 工具相关的字段
    tool: str = ""  # 调用工具的名字
    tool_input: dict = Field(default_factory=dict)  # 工具的输入

    # 消息相关的数据
    message: list[dict] = Field(default_factory=dict)  # 推理使用的消息列表
    message_token_count: int = 0  # 消息花费的token数
    message_unit_price: float = 0  # 单价
    message_price_unit: float = 0  # 价格单位

    # 答案相关的数据
    answer: str = ""  # LLM生成的最终答案
    answer_token_count: int = 0  # LLM生成答案的token数
    answer_unit_price: float = 0  # 单价
    answer_price_unit: float = 0  # 价格单位

    # Agent推理统计相关
    total_token_count: int = 0  # 总token消耗数量
    total_price: float = 0  # 总价格
    latency: float = 0  # 步骤推理耗时


class AgentResult(BaseModel):
    """智能体推理观察最终结果"""
    query: str = ""  # 原始用户提问
    image_urls: list[str] = Field(default_factory=list)  # 用户的图片输入列表

    message: list[dict] = Field(default_factory=list)  # 产生最终答案的消息列表
    message_token_count: int = 0  # 消息花费的token数
    message_unit_price: float = 0  # 单价
    message_price_unit: float = 0  # 价格单位

    answer: str = ""  # Agent产生的最终答案
    answer_token_count: int = 0  # LLM生成答案的token数
    answer_unit_price: float = 0  # 单价
    answer_price_unit: float = 0  # 价格单位

    total_token_count: int = 0  # 总token消耗数量
    total_price: float = 0  # 总价格
    latency: float = 0  # 总耗时

    status: str = MessageStatus.NORMAL.value  # 消息的状态
    error: str = ""  # 错误信息

    agent_thoughts: list[AgentThought] = Field(default_factory=list)  # 产生答案的推理步骤
