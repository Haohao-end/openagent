from pydantic import BaseModel, Field
from enum import Enum
# 摘要汇总模板
SUMMARIZER_TEMPLATE = """你是会话长期记忆整理助手。请基于“当前总结”和“新的会话”生成新的增量总结。

规则：
1. 仅保留对后续对话有价值的信息：用户目标、约束条件、偏好、关键事实、已做决策、未解决事项。
2. 若新旧信息冲突，以“新的会话”为准，并在总结中体现已更新。
3. 不得编造，不得补充对话中未出现的事实。
4. 中英混合场景优先中文表达，保留必要专有名词英文写法（如 OpenAI、DeepSeek、API、SQL）。
5. 输出仅包含最终总结正文，不要标题、不要列表、不要额外解释。
6. 总结尽量精炼，建议不超过 300 个中文字符（信息复杂时可适度放宽）。

当前总结:
{summary}

新的会话:
{new_lines}

新的总结:"""

# 会话名字提示模板
CONVERSATION_NAME_TEMPLATE = """请从用户输入中提取会话主题，并严格按结构化字段返回。

规则：
1. subject 必须准确反映用户核心意图，避免“聊天”“咨询”等空泛表达。
2. 标题可以适当详细：中文建议 8-30 个字；英文建议 5-14 个词。
3. 输出语言与用户主语言一致；中英混合场景优先中文，并保留必要专有名词英文。
4. language_type 需明确标注语言类型（如纯中文/纯英文/中英混合/其他语言）。
5. reasoning 仅用一句话简述语言判断依据，保持简洁。
6. 若意图不明确，subject 使用“未明确主题咨询”（或对应语言表达）。
7. 仅返回 schema 对应字段，不要输出额外文本。"""

# 建议问题提示词模板
SUGGESTED_QUESTIONS_TEMPLATE = """你是对话续问生成助手。请基于历史信息预测用户下一步最可能提出的三个问题。

规则：
1. 每个问题必须与历史上下文强相关，且具体可执行。
2. 避免空泛问题（如“还有吗”“怎么做”）和重复问题。
3. 每个问题长度不超过 50 个字符。
4. 输出语言与用户主语言一致；中英混合场景优先中文，并保留必要专有名词英文。
5. 仅返回 schema 对应的 questions 数组，不要输出额外文本。"""

class ConversationInfo(BaseModel):
    """从用户输入中提取语言类型、语言判断依据和会话主题标题。
    输出需简洁准确，并与用户主语言一致；中英混合场景优先中文。"""
    language_type: str = Field(description="用户输入的语言类型声明，如纯中文、纯英文或中英混合")
    reasoning: str = Field(description="语言判断依据，使用一句简洁描述")
    subject: str = Field(description=(
        "会话主题标题，需准确概括用户核心意图。"
        "输出语言与用户主语言一致，标题可以稍长且信息完整，避免空泛表述。"
    ))

class SuggestedQuestions(BaseModel):
    """基于历史会话生成最可能的三个后续问题，每个问题不超过 50 个字符。"""
    questions: list[str] = Field(description="建议问题列表，类型为字符串数组")

class InvokeFrom(str, Enum):
    """会话调用来源"""
    SERVICE_API = "service_api"  # 开放api服务调用
    WEB_APP = "web_app"  # web应用
    DEBUGGER = "debugger"  # 调试页面
    ASSISTANT_AGENT = "assistant_agent"  # 辅助Agent调用


class MessageStatus(str, Enum):
    """会话状态"""
    NORMAL = "normal"  # 正常
    STOP = "stop"  # 停止
    TIMEOUT = "timeout"  # 超时
    ERROR = "error"  # 出错


