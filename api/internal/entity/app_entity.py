from enum import Enum


# 生成icon描述提示词模板
GENERATE_ICON_PROMPT_TEMPLATE = """你是一个拥有10年经验的AI绘画提示词工程师，擅长将用户提供的`应用名称`和`应用描述`，转换成高质量应用图标的英文提示词。

你的任务：
1. 先理解应用的核心功能、目标用户、品牌气质和视觉隐喻。
2. 自动补全一个优秀 app icon 所需的关键视觉维度，包括但不限于：
   - main subject / symbolic metaphor
   - visual style
   - shape and container
   - color palette
   - material / texture
   - lighting
   - composition
   - background
   - quality cues
   - negative constraints
3. 输出时只生成**一条英文 prompt**，不要输出解释、标题、列表、引号或任何额外内容。

用户输入如下：
应用名称: {name}
应用描述: {description}

生成要求：
- 输出必须是英文。
- 输出必须适合生成“移动应用 icon / app launcher icon”。
- 图标主体必须单一、清晰、居中，易识别，避免复杂场景。
- 默认采用现代、精致、商业可用的设计语言。
- 优先保证在小尺寸下仍然可辨识。
- 如果应用描述偏工具型 / SaaS / 效率类，优先使用 minimalist / flat / clean / modern 风格。
- 如果应用描述偏娱乐 / 社交 / 游戏 / 儿童类，可适当增强 3D / glossy / playful / vibrant 风格。
- 除非描述明确要求，否则不要生成文字、字母、数字、logo 文案、水印、边框装饰或复杂背景。
- 默认背景为 clean plain background 或 subtle gradient background，使主体突出。
- 默认使用 rounded square app icon composition，除非应用气质更适合 circle / freeform。
- prompt 中应明确包含以下信息：
  - what the icon depicts
  - style keywords
  - color direction
  - material/finish
  - lighting
  - centered composition
  - clean background
  - no text, no watermark, no extra elements

请直接输出最终英文 prompt，除此之外什么都不要输出。"""

class AppStatus(str, Enum):
    """应用状态枚举类"""
    DRAFT = "draft"
    PUBLISHED = "published"


class AppConfigType(str, Enum):
    """应用配置类型枚举类"""
    DRAFT = "draft"
    PUBLISHED = "published"


# 应用默认配置信息
DEFAULT_APP_CONFIG = {
    "model_config": {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "parameters": {
            "temperature": 1,
            "top_p": 1,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "max_tokens": 8192,
        },
    },
    "dialog_round": 3,
    "preset_prompt": "",
    "tools": [],
    "workflows": [],
    "datasets": [],
    "retrieval_config": {
        "retrieval_strategy": "semantic",
        "k": 10,
        "score": 0.5,
    },
    "long_term_memory": {
        "enable": True,
    },
    "opening_statement": "",
    "opening_questions": [],
    "speech_to_text": {
        "enable": True,
    },
    "text_to_speech": {
        "enable": True,
        "voice": "alex",
        "auto_play": True,
    },
    "suggested_after_answer": {
        "enable": True,
    },
    "review_config": {
        "enable": False,
        "keywords": [],
        "inputs_config": {
            "enable": False,
            "preset_response": "",
        },
        "outputs_config": {
            "enable": False,
        },
    },
}
