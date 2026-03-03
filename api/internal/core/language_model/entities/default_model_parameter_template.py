from .model_entity import DefaultModelParameterName, ModelParameterType

# 默认模型参数模板，用于减少YAML的配置，参数以OpenAI的模型接口作为标准
DEFAULT_MODEL_PARAMETER_TEMPLATE = {
    # 温度模板默认参数
    DefaultModelParameterName.TEMPERATURE.value: {
        "label": "温度",
        "type": ModelParameterType.FLOAT.value,
        "help": "温度控制随机性，较低的温度会导致较少的随机生成。随着温度接近零，模型将变得更确定，较高的温度会导致更多随机内容被生成",
        "required": False,
        "default": 1,
        "min": 0,
        "max": 2,
        "precision": 2,
        "options": [],
    },
    # TopP核采样
    DefaultModelParameterName.TOP_P.value: {
        "label": "Top P",
        "type": ModelParameterType.FLOAT.value,
        "help": "通过核心采样控制多样性，0.5表示考虑了一半的所有可能性加权选项",
        "required": False,
        "default": 0,
        "min": 0,
        "max": 1,
        "precision": 2,
        "options": [],
    },
    # 存在惩罚
    DefaultModelParameterName.PRESENCE_PENALTY.value: {
        "label": "存在惩罚",
        "type": ModelParameterType.FLOAT.value,
        "help": "对文本中已有的标记的对数概率施加惩罚。",
        "required": False,
        "default": 0,
        "min": -2.0,
        "max": 2.0,
        "precision": 2,
        "options": [],
    },
    # 频率惩罚
    DefaultModelParameterName.FREQUENCY_PENALTY.value: {
        "label": "频率惩罚",
        "type": ModelParameterType.FLOAT.value,
        "help": "对文本中已有的标记的对数概率施加惩罚。",
        "required": False,
        "default": 0,
        "min": -2.0,
        "max": 2.0,
        "precision": 2,
        "options": [],
    },
    # 最大生成tokens数
    DefaultModelParameterName.MAX_TOKENS.value: {
        "label": "最大标记",
        "type": ModelParameterType.INT.value,
        "help": "要生成的标记的最大数量，类型为整型",
        "required": False,
        "default": None,
        "min": 1,
        "max": 16384,
        "precision": 0,
        "options": [],
    },
}
