"""标签分配服务 - 处理应用/工作流的自动标签分配"""
import logging
from typing import List

from pydantic import BaseModel, Field

from internal.entity.tag_entity import (
    TAG_KEYWORDS_MAPPING,
    APP_TAG_PRIORITY,
    sort_tags_by_priority,
)
from internal.core.language_model.providers.deepseek.chat import Chat
from internal.core.language_model.entities.model_entity import ModelFeature


class TagAssignmentInput(BaseModel):
    """标签分配输入结构"""
    tags: List[str] = Field(
        description="选择的标签列表，最多选择3个最相关的标签。如果无法确定，选择'other'",
        min_length=1,
        max_length=3
    )


class TagAssignmentService:
    """标签分配服务"""

    @staticmethod
    def match_tags_by_keywords(name: str, description: str) -> List[str]:
        """
        基于关键词匹配分配标签（第一层）

        Args:
            name: 应用/工作流名称
            description: 应用/工作流描述

        Returns:
            匹配到的标签列表，按优先级排序
        """
        text = f"{name} {description}".lower()
        matched_tags = {}

        for tag_id, tag_info in TAG_KEYWORDS_MAPPING.items():
            if tag_id == "other":  # 跳过"其他"标签
                continue

            # 计算匹配分数
            match_score = 0
            for keyword in tag_info["keywords"]:
                if keyword.lower() in text:
                    # 名称中的匹配权重更高
                    if keyword.lower() in name.lower():
                        match_score += 2
                    else:
                        match_score += 1

            if match_score > 0:
                matched_tags[tag_id] = {
                    "priority": tag_info["priority"],
                    "score": match_score
                }

        # 按优先级排序，返回标签ID列表
        if matched_tags:
            sorted_tags = sorted(
                matched_tags.items(),
                key=lambda x: x[1]["priority"]
            )
            return [tag_id for tag_id, _ in sorted_tags]

        return []

    @staticmethod
    def assign_tags_by_deepseek(name: str, description: str) -> List[str]:
        """
        使用DeepSeek模型通过FunctionCall分配标签（第二层）

        Args:
            name: 应用/工作流名称
            description: 应用/工作流描述

        Returns:
            分配的标签列表
        """
        try:
            # 创建LLM实例
            llm = Chat(
                model="deepseek-chat",
                temperature=0.3,
                features=[ModelFeature.TOOL_CALL.value],
                metadata={},
            )

            # 定义FunctionCall工具
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "assign_tags",
                        "description": "根据应用/工作流的名称和描述，从预定义的13个标签中选择最相关的1个或多个标签",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "tags": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": [
                                            "general", "writing", "coding", "business",
                                            "education", "entertainment", "productivity",
                                            "customer_service", "data_analysis", "translation",
                                            "marketing", "research", "other"
                                        ]
                                    },
                                    "description": "选择的标签列表，最多选择3个最相关的标签。如果无法确定，选择'other'",
                                    "minItems": 1,
                                    "maxItems": 3
                                }
                            },
                            "required": ["tags"]
                        }
                    }
                }
            ]

            # 构建提示词
            prompt = f"""你是一个应用分类专家。根据给定的应用/工作流名称和描述，从以下13个预定义标签中选择最相关的1-3个标签。

可选标签：
1. 通用 (general) - 通用型工具，适用多个场景
2. 写作助手 (writing) - 文案、内容、文章生成
3. 编程助手 (coding) - 代码生成、调试、优化
4. 商业分析 (business) - 商业决策、数据分析、市场研究
5. 教育学习 (education) - 教学、学习、培训、考试
6. 娱乐休闲 (entertainment) - 游戏、娱乐、创意
7. 效率工具 (productivity) - 任务管理、时间管理、自动化
8. 客户服务 (customer_service) - 客服、支持、反馈
9. 数据分析 (data_analysis) - 数据处理、可视化、统计
10. 翻译 (translation) - 多语言翻译、本地化
11. 营销 (marketing) - 营销策略、广告、推广
12. 研究 (research) - 学术研究、论文、知识库
13. 其他 (other) - 不属于上述任何分类

应用/工作流信息：
- 名称: {name}
- 描述: {description}

请选择最相关的标签。优先选择具体的功能标签，只有在无法确定时才选择"通用"或"其他"。"""

            # 调用LLM
            response = llm.invoke(prompt)

            # 解析响应中的标签
            # 这里需要根据实际的LLM响应格式进行解析
            # 假设LLM返回的是JSON格式的FunctionCall结果
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    if tool_call.get('name') == 'assign_tags':
                        tags = tool_call.get('args', {}).get('tags', [])
                        if tags:
                            return sort_tags_by_priority(tags)

            # 如果解析失败，返回空列表
            return []

        except Exception as e:
            logging.exception(f"使用DeepSeek分配标签失败: {str(e)}")
            return []

    @staticmethod
    def auto_assign_tags(name: str, description: str) -> List[str]:
        """
        自动分配标签 - 先用关键词匹配，失败则调用DeepSeek

        Args:
            name: 应用/工作流名称
            description: 应用/工作流描述

        Returns:
            分配的标签列表
        """
        # 第一层：关键词匹配
        tags = TagAssignmentService.match_tags_by_keywords(name, description)

        if tags:
            return tags

        # 第二层：调用DeepSeek
        tags = TagAssignmentService.assign_tags_by_deepseek(name, description)

        if tags:
            return tags

        # 如果都失败，返回"其他"标签
        return ["other"]

    @staticmethod
    def assign_tags_for_assistant_agent(name: str, description: str) -> List[str]:
        """
        为辅助Agent创建的应用分配标签 - 直接使用DeepSeek FunctionCall

        Args:
            name: 应用/工作流名称
            description: 应用/工作流描述

        Returns:
            分配的标签列表
        """
        tags = TagAssignmentService.assign_tags_by_deepseek(name, description)

        if tags:
            return tags

        # 如果失败，尝试关键词匹配
        tags = TagAssignmentService.match_tags_by_keywords(name, description)

        if tags:
            return tags

        # 如果都失败，返回"其他"标签
        return ["other"]
