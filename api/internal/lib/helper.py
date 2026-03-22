import importlib
import random
import string
from datetime import datetime
from enum import Enum
from hashlib import sha3_256
from typing import Any
from uuid import UUID
from langchain_core.documents import Document
from pydantic import BaseModel

def dynamic_import(module_name: str, symbol_name: str) -> Any:
    """动态导入特定模块下的特定功能"""
    module = importlib.import_module(module_name)
    return getattr(module, symbol_name)


def add_attribute(attr_name: str, attr_value: Any):
    """装饰器函数，为特定的函数添加相应的属性，第一个参数为属性名字，第二个参数为属性值"""

    def decorator(func):
        setattr(func, attr_name, attr_value)
        return func

    return decorator


def generate_text_hash(text: str) -> str:
    """根据传递的文本计算对应的哈希值"""
    # 1.将需要计算哈希值的内容加上None这个字符串，避免传递了空字符串导致计算出错
    text = str(text) + "None"

    # 2.使用sha3_256将数据转换成哈希值后返回
    return sha3_256(text.encode()).hexdigest()


def datetime_to_timestamp(dt: datetime) -> int:
    """将传入的datetime时间转换成时间戳，如果数据不存在则返回0"""
    if dt is None:
        return 0
    # 数据库中的 datetime 是 UTC 时间（无时区信息），需要明确指定为 UTC
    from datetime import timezone
    if dt.tzinfo is None:
        # 如果没有时区信息，假设为 UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def combine_documents(documents: list[Document]) -> str:
    """将对应的文档列表使用换行符进行合并"""
    return "\n\n".join([document.page_content for document in documents])


def remove_fields(data_dict: dict, fields: list[str]) -> None:
    """根据传递的字段名移除字典中指定的字段"""
    for field in fields:
        data_dict.pop(field, None)


def convert_model_to_dict(obj: Any, *args, **kwargs) -> Any:
    """
    将Pydantic模型、UUID、Enum等对象转换为可序列化的字典或基本类型
    支持 Pydantic V1 和 V2 版本
    """
    # 处理None值
    if obj is None:
        return None

    # 处理Pydantic V2模型
    if hasattr(obj, "model_dump"):
        obj_dict = obj.model_dump(*args, **kwargs)
        # 递归处理嵌套字段
        for key, value in obj_dict.items():
            obj_dict[key] = convert_model_to_dict(value, *args, **kwargs)
        return obj_dict

    # 处理Pydantic V1模型
    elif hasattr(obj, "dict"):
        obj_dict = obj.dict(*args, **kwargs)
        for key, value in obj_dict.items():
            obj_dict[key] = convert_model_to_dict(value, *args, **kwargs)
        return obj_dict

    # 处理 UUID 类型
    elif isinstance(obj, UUID):
        return str(obj)

    # 处理 Enum 类型
    elif isinstance(obj, Enum):
        return obj.value

    # 处理 datetime 类型
    elif isinstance(obj, datetime):
        return obj.isoformat()

    # 处理列表类型
    elif isinstance(obj, list):
        return [convert_model_to_dict(item, *args, **kwargs) for item in obj]

    # 处理字典类型
    elif isinstance(obj, dict):
        return {key: convert_model_to_dict(value, *args, **kwargs) for key, value in obj.items()}

    # 其他基本类型直接返回
    return obj


def get_value_type(value: Any) -> Any:
    """根据传递的值获取变量的类型 并将str和bool转换成string和boolean"""
    # 1.计算变量的类型并且转换为字符串
    value_type = type(value).__name__

    # 2.判断是否为str或者bool
    if value_type == "str":
        return "string"
    elif value_type == "bool":
        return "boolean"

    return value_type

def generate_random_string(length: int = 16) -> str:
    """根据传递的位数 生成随机的字符串"""
    # 1.定义字符集 包含大小写字母和数字
    chars = string.ascii_letters + string.digits

    # 2.使用random.choices生成指定长度的随机字符串
    random_str = ''.join(random.choices(chars, k=length))

    return random_str