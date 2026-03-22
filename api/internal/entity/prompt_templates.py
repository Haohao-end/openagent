"""
提示词模板集合

包含所有系统级别的提示词模板，用于 LLM 调用。
"""

# 应用优化提示词
OPTIMIZE_PROMPT_TEMPLATE = """你是一个专业的应用优化助手。请根据用户反馈和使用数据，提供应用改进建议。

用户反馈:
{feedback}

当前应用配置:
{config}

请提供具体的优化建议，包括：
1. 功能改进
2. 用户体验优化
3. 性能优化
4. 安全性增强

优化建议:"""

# Python 代码助手提示词
PYTHON_CODE_ASSISTANT_PROMPT = """你是一个专业的 Python 代码助手。请帮助用户编写、调试和优化 Python 代码。

用户需求:
{requirement}

当前代码:
{code}

请提供：
1. 完整的代码实现
2. 代码说明和注释
3. 可能的改进建议
4. 测试用例示例

代码实现:"""

# OpenAPI Schema 助手提示词
OPENAPI_SCHEMA_ASSISTANT_PROMPT = """你是一个专业的 OpenAPI Schema 设计助手。请帮助用户设计和优化 API 接口。

API 需求:
{requirement}

当前 Schema:
{schema}

请提供：
1. 完整的 OpenAPI 3.0 Schema 定义
2. 请求/响应示例
3. 错误处理定义
4. 安全性配置

OpenAPI Schema:"""

# 图标生成提示词
GENERATE_ICON_PROMPT_TEMPLATE = """你是一个专业的图标设计提示词生成助手。请根据应用信息生成适合的图标设计提示词。

应用名称: {app_name}
应用描述: {app_description}
应用类别: {app_category}

请生成一个详细的图标设计提示词，用于 DALL-E 或其他图像生成模型。
提示词应该包括：
1. 图标风格（如 flat, 3D, minimalist 等）
2. 主要元素和符号
3. 颜色建议
4. 尺寸和比例要求

图标设计提示词:"""
