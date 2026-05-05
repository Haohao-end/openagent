import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from injector import inject
from langchain_core.messages import trim_messages, BaseMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from redis import Redis

from internal.core.language_model.providers.deepseek.chat import Chat
from internal.exception import FailException
from .base_service import BaseService


@inject
@dataclass
class IntentRecognitionService(BaseService):
    """意图识别服务"""
    redis_client: Redis

    INTENT_CACHE_TTL = 24 * 60 * 60  # 24小时
    MAX_TOKENS = 4000
    DEFAULT_INTENT = {
        "intent": "你好，欢迎来到 OpenAgent 🎉\n\n我可以帮你从想法出发，快速创建专属 AI 应用。\n我支持根据你的需求执行 function call，自动调用工具并生成垂直 Agent 的后端能力代码与配置。\n你可以把应用一键发布到 OpenAgent 平台、微信等多个渠道，也可以部署到你自己的网站。",
        "confidence": 0,
        "suggested_actions": [
            {
                "label": "我想做一个应用",
                "action": "create_app",
                "icon": "plus"
            },
            {
                "label": "帮我创建一个天气智能体",
                "action": "create_weather_agent",
                "icon": "cloud"
            },
            {
                "label": "你能做什么？",
                "action": "view_capabilities",
                "icon": "help"
            }
        ],
        "is_default": True
    }

    PROMPT_TEMPLATE = """你是一个用户意图识别专家。根据用户最近的对话历史，识别用户最可能想做的事情。

用户最近的对话历史：
{messages}

请分析用户的意图，并返回以下JSON格式的结果：
{{
  "intent": "用户想做的事情的简洁描述（一句话）",
  "confidence": 0.0-1.0之间的置信度,
  "suggested_actions": [
    {{
      "label": "操作标签",
      "action": "操作标识符",
      "icon": "图标名称"
    }}
  ]
}}

可选的操作标识符：
- create_app: 创建应用
- view_apps: 查看应用
- create_workflow: 创建工作流
- view_workflows: 查看工作流
- create_dataset: 创建数据集
- view_datasets: 查看数据集
- view_examples: 查看示例
- view_capabilities: 查看功能

请确保返回有效的JSON格式。"""

    def recognize(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """
        识别用户意图

        Args:
            messages: 消息列表，每条消息包含 role 和 content

        Returns:
            意图识别结果
        """
        try:
            # 1. 构建LangChain消息列表
            lc_messages = self._build_langchain_messages(messages)

            # 2. 使用trim_messages限制token
            model = Chat(model="deepseek-chat")
            trimmed_messages = trim_messages(
                messages=lc_messages,
                max_tokens=self.MAX_TOKENS,
                token_counter=model,
                strategy="last",
                start_on="human",
                end_on="ai",
            )

            # 3. 构建prompt
            messages_text = self._format_messages(trimmed_messages)
            prompt_text = self.PROMPT_TEMPLATE.format(messages=messages_text)

            # 4. 调用DeepSeek模型
            model = Chat(model="deepseek-chat")
            response = model.invoke(prompt_text)

            # 5. 解析响应
            result = self._parse_response(response)

            return result

        except Exception as e:
            logging.error(f"Intent recognition failed: {str(e)}")
            raise FailException(f"意图识别失败: {str(e)}")

    def _build_langchain_messages(self, messages: list[dict[str, str]]) -> list[BaseMessage]:
        """构建LangChain消息列表"""
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "").lower()
            content = msg.get("content", "")

            if role == "user" or role == "human":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant" or role == "ai":
                lc_messages.append(AIMessage(content=content))

        return lc_messages

    def _format_messages(self, messages: list[BaseMessage]) -> str:
        """格式化消息为文本"""
        formatted = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted.append(f"用户: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted.append(f"助手: {msg.content}")

        return "\n".join(formatted)

    def _parse_response(self, response: str) -> dict[str, Any]:
        """解析模型响应"""
        try:
            # 尝试从响应中提取JSON
            json_str = response

            # 如果响应包含markdown代码块，提取其中的JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            result = json.loads(json_str)

            # 验证必要字段
            if "intent" not in result or "confidence" not in result or "suggested_actions" not in result:
                logging.warning("Invalid response format from model")
                return self.DEFAULT_INTENT

            result["is_default"] = False
            return result

        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse model response: {str(e)}")
            return self.DEFAULT_INTENT

    @classmethod
    def _get_cache_key(cls, user_id: str) -> str:
        """获取缓存key"""
        return f"home:intent:{user_id}"

    def get_cached_intent(self, user_id: str) -> dict[str, Any] | None:
        """从Redis获取缓存的意图识别结果"""
        try:
            cache_key = self._get_cache_key(user_id)
            cached_data = self.redis_client.get(cache_key)

            if not cached_data:
                return None

            return json.loads(cached_data)
        except Exception as e:
            logging.error(f"Failed to get cached intent: {str(e)}")
            return None

    def cache_intent(self, user_id: str, intent_result: dict[str, Any]) -> None:
        """将意图识别结果缓存到Redis"""
        try:
            cache_key = self._get_cache_key(user_id)
            intent_result["generated_at"] = datetime.now(UTC).isoformat()
            intent_result["expires_at"] = (datetime.now(UTC) + timedelta(hours=24)).isoformat()

            self.redis_client.setex(
                cache_key,
                self.INTENT_CACHE_TTL,
                json.dumps(intent_result, ensure_ascii=False)
            )
        except Exception as e:
            logging.error(f"Failed to cache intent: {str(e)}")

    def clear_cache(self, user_id: str) -> None:
        """清除缓存"""
        try:
            cache_key = self._get_cache_key(user_id)
            self.redis_client.delete(cache_key)
        except Exception as e:
            logging.error(f"Failed to clear cache: {str(e)}")
