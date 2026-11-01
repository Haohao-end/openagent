import importlib
import json
import random
import re
import string
from datetime import UTC, datetime, time as dt_time
from enum import Enum
from hashlib import sha3_256
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit
from uuid import UUID
from langchain_core.documents import Document
from pydantic import BaseModel

_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".svg",
    ".tif",
    ".tiff",
    ".avif",
}
_IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".avif": "image/avif",
}
_MARKDOWN_IMAGE_URL_PATTERN = re.compile(r"!\[[^\]]*]\((https?://[^\s)]+)\)", re.IGNORECASE)
_STRUCTURED_IMAGE_URL_PATTERN = re.compile(
    r"图片\s*\d+\s*:\s*(?:\n\s*)?URL\s*:\s*(https?://[^\s)]+)",
    re.IGNORECASE,
)
_RAW_IMAGE_URL_PATTERN = re.compile(
    r"https?://[^\s<>()]+?\.(?:png|jpg|jpeg|gif|webp|bmp|svg|tiff|tif|avif)(?:\?[^\s<>()]*)?",
    re.IGNORECASE,
)
_TRAILING_URL_PUNCTUATION = ".,;)]}"
_DEFAULT_IMAGE_GROUP_NAME = "生成图片"
_PUBLIC_URL_SECRET_QUERY_KEYS = {
    "access_token", "api_key", "apikey", "auth", "authorization", "client_secret", "key", "password",
    "awsaccesskeyid", "credential", "googleaccessid", "refresh_token", "secret",
    "security_token", "sig", "signature", "token", "x_api_key",
    "api_token", "oauth_token", "x_auth_token", "x_mcp_token",
    "x_amz_credential", "x_amz_security_token", "x_amz_signature",
    "x_goog_credential", "x_goog_signature",
}


def sanitize_public_url(value: Any) -> str:
    """Remove embedded credentials and common secret query parameters from a public URL."""
    url = str(value or "")
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""

    netloc = parts.netloc.rsplit("@", 1)[-1]
    query = parse_qsl(parts.query, keep_blank_values=True)
    public_query = [
        (key, item)
        for key, item in query
        if key.lower().replace("-", "_") not in _PUBLIC_URL_SECRET_QUERY_KEYS
    ]
    if netloc == parts.netloc and public_query == query:
        return url
    return urlunsplit(parts._replace(netloc=netloc, query=urlencode(public_query, doseq=True)))


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


def datetime_to_timestamp(dt: datetime | int | float | None) -> int:
    """将时间对象或已归一化的时间戳转换成秒级时间戳。"""
    if dt is None:
        return 0

    if isinstance(dt, (int, float)):
        return int(dt)

    # 数据库中的 datetime 是 UTC 时间（无时区信息），需要明确指定为 UTC
    from datetime import timezone
    if dt.tzinfo is None:
        # 如果没有时区信息，假设为 UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(UTC)


def utc_now_naive() -> datetime:
    """返回无时区的 UTC 时间，兼容当前项目的 DateTime 列。"""
    return utc_now().replace(tzinfo=None)


def ensure_utc_naive(dt: datetime | None) -> datetime | None:
    """将任意 datetime 归一化为无时区的 UTC 时间。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


def utc_midnight_naive(reference: datetime | None = None) -> datetime:
    """返回指定时间所在 UTC 自然日的 00:00:00（无时区）。"""
    normalized = ensure_utc_naive(reference or utc_now())
    return datetime.combine(normalized.date(), dt_time.min)


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


def build_image_part(image_url: str) -> dict[str, Any]:
    """构建统一的图片 part 结构。"""
    return {
        "type": "image",
        "url": str(image_url or "").strip(),
    }


def build_input_parts(query: str, image_urls: list[str] | None = None) -> list[dict[str, Any]]:
    """根据 query 与图片列表构建统一输入 parts。"""
    normalized_query = str(query or "")
    normalized_image_urls = [str(item or "").strip() for item in (image_urls or []) if str(item or "").strip()]

    parts: list[dict[str, Any]] = []
    if normalized_query != "":
        parts.append({
            "type": "text",
            "text": normalized_query,
        })
    parts.extend(build_image_part(image_url) for image_url in normalized_image_urls)
    return parts


def _guess_image_extension(url: str) -> str:
    """根据 URL 后缀推断图片扩展名。"""
    normalized_path = urlparse(_clean_output_url(url)).path.lower()
    for extension in sorted(_IMAGE_EXTENSIONS, key=len, reverse=True):
        if normalized_path.endswith(extension):
            return extension.lstrip(".")
    return ""


def _guess_image_mime_type(url: str) -> str:
    """根据 URL 后缀推断图片 MIME 类型。"""
    extension = _guess_image_extension(url)
    if not extension:
        return ""
    return _IMAGE_MIME_TYPES.get(f".{extension}", "")


def _clean_output_url(url: Any) -> str:
    """清洗输出中的 URL，去掉常见的尾部标点。"""
    normalized_url = str(url or "").strip()
    while normalized_url and normalized_url[-1] in _TRAILING_URL_PUNCTUATION:
        normalized_url = normalized_url[:-1]
    return normalized_url


def _is_image_url(url: Any) -> bool:
    """判断 URL 是否明显指向图片资源。"""
    normalized_url = _clean_output_url(url)
    if normalized_url == "":
        return False
    return any(urlparse(normalized_url).path.lower().endswith(ext) for ext in _IMAGE_EXTENSIONS)


def _is_image_artifact(artifact: dict[str, Any]) -> bool:
    """判断附件是否应被渲染为图片。"""
    mime_type = str(artifact.get("mime_type", "") or "").strip().lower()
    extension = str(artifact.get("extension", "") or "").strip().lower()
    if mime_type.startswith("image/"):
        return True
    if extension:
        normalized_extension = extension if extension.startswith(".") else f".{extension}"
        if normalized_extension in _IMAGE_EXTENSIONS:
            return True
    return _is_image_url(artifact.get("url", ""))


def _normalize_output_artifact(artifact: Any) -> dict[str, Any] | None:
    """归一化附件结构，输出稳定的用户侧字段。"""
    if not isinstance(artifact, dict):
        return None

    normalized_url = _clean_output_url(artifact.get("url", ""))
    if normalized_url == "":
        return None

    path = str(artifact.get("path", "") or "").strip()
    path_name = path.rsplit("/", 1)[-1] if path else ""
    url_path_name = urlparse(normalized_url).path.rsplit("/", 1)[-1] if normalized_url else ""
    normalized_name = str(artifact.get("name", "") or "").strip() or path_name or url_path_name or normalized_url

    normalized_artifact: dict[str, Any] = {
        "name": normalized_name,
        "url": normalized_url,
    }

    for key in ("id", "mime_type", "extension", "group_id", "group_name"):
        value = str(artifact.get(key, "") or "").strip()
        if value != "":
            normalized_artifact[key] = value

    size = artifact.get("size")
    if size is not None:
        try:
            normalized_artifact["size"] = int(size)
        except (TypeError, ValueError):
            pass

    if not str(normalized_artifact.get("extension", "") or "").strip():
        guessed_extension = _guess_image_extension(normalized_url)
        if guessed_extension:
            normalized_artifact["extension"] = guessed_extension

    if not str(normalized_artifact.get("mime_type", "") or "").strip():
        guessed_mime_type = _guess_image_mime_type(normalized_url)
        if guessed_mime_type:
            normalized_artifact["mime_type"] = guessed_mime_type

    return normalized_artifact


def _merge_artifact(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """合并重复附件，优先保留更完整的数据。"""
    merged = dict(existing)
    for key, value in incoming.items():
        if key not in merged or merged[key] in ("", None):
            merged[key] = value
        elif key == "size" and int(merged.get("size", 0) or 0) <= 0:
            merged[key] = value
    return merged


def _build_image_group_metadata(agent_thought: Any) -> dict[str, str]:
    """为同一轮图片生成结果构建稳定分组信息。"""
    group_id = str(_read_object_field(agent_thought, "id", "") or "").strip()
    if not group_id:
        return {}
    return {
        "group_id": group_id,
        "group_name": _DEFAULT_IMAGE_GROUP_NAME,
    }


def _read_object_field(value: Any, field: str, default: Any = None) -> Any:
    """兼容 dict / 对象 两种访问方式。"""
    if isinstance(value, dict):
        return value.get(field, default)
    return getattr(value, field, default)


def extract_output_artifacts(agent_thoughts: list[Any] | None = None) -> list[dict[str, Any]]:
    """从推理事件中提取稳定的多模态附件输出。"""
    artifacts_by_url: dict[str, dict[str, Any]] = {}

    for agent_thought in agent_thoughts or []:
        tool_input = _read_object_field(agent_thought, "tool_input", {}) or {}
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except Exception:
                tool_input = {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        artifact = _normalize_output_artifact(tool_input.get("artifact"))
        if artifact is None:
            event = _read_object_field(agent_thought, "event", "")
            normalized_event = str(getattr(event, "value", event) or "").strip().lower()
            if normalized_event == "deep_artifact_created":
                artifact = _normalize_output_artifact({
                    "name": _read_object_field(agent_thought, "thought", ""),
                    "url": _read_object_field(agent_thought, "observation", ""),
                })
        if artifact is None:
            combined_text = "\n".join(
                [
                    str(_read_object_field(agent_thought, "thought", "") or "").strip(),
                    str(_read_object_field(agent_thought, "observation", "") or "").strip(),
                ]
            ).strip()
            if not combined_text:
                continue

            inline_urls = _extract_inline_image_urls(combined_text, existing_urls=set(artifacts_by_url.keys()))
            if not inline_urls:
                continue

            group_metadata = _build_image_group_metadata(agent_thought)
            for inline_index, inline_url in enumerate(inline_urls, start=1):
                inline_artifact = _normalize_output_artifact({
                    "name": _DEFAULT_IMAGE_GROUP_NAME if len(inline_urls) == 1 else f"{_DEFAULT_IMAGE_GROUP_NAME} {inline_index}",
                    "url": inline_url,
                    **group_metadata,
                })
                if inline_artifact is None:
                    continue
                if inline_url in artifacts_by_url:
                    artifacts_by_url[inline_url] = _merge_artifact(artifacts_by_url[inline_url], inline_artifact)
                else:
                    artifacts_by_url[inline_url] = inline_artifact
            continue

        if _is_image_artifact(artifact):
            group_metadata = _build_image_group_metadata(agent_thought)
            for key, value in group_metadata.items():
                if not str(artifact.get(key, "") or "").strip():
                    artifact[key] = value

        artifact_url = artifact["url"]
        if artifact_url in artifacts_by_url:
            artifacts_by_url[artifact_url] = _merge_artifact(artifacts_by_url[artifact_url], artifact)
        else:
            artifacts_by_url[artifact_url] = artifact

    return list(artifacts_by_url.values())


def _build_artifact_part(artifact: dict[str, Any]) -> dict[str, Any]:
    """根据附件构建 artifact 输出 part。"""
    return {
        key: value
        for key, value in {
            "type": "artifact",
            "name": artifact.get("name", ""),
            "url": artifact.get("url", ""),
            "mime_type": artifact.get("mime_type", ""),
            "extension": artifact.get("extension", ""),
            "size": artifact.get("size"),
            "group_id": artifact.get("group_id", ""),
            "group_name": artifact.get("group_name", ""),
        }.items()
        if value not in ("", None)
    }


def _build_output_image_part(
    image_url: str,
    *,
    name: str = "",
    mime_type: str = "",
    extension: str = "",
    group_id: str = "",
    group_name: str = "",
) -> dict[str, Any]:
    """构建输出侧图片 part。"""
    return {
        key: value
        for key, value in {
            "type": "image",
            "url": _clean_output_url(image_url),
            "name": str(name or "").strip(),
            "mime_type": str(mime_type or "").strip(),
            "extension": str(extension or "").strip(),
            "group_id": str(group_id or "").strip(),
            "group_name": str(group_name or "").strip(),
        }.items()
        if value not in ("", None)
    }


def _extract_inline_image_urls(answer: str, existing_urls: set[str] | None = None) -> list[str]:
    """从文本中提取图片 URL，兼容文生图工具的纯文本返回。"""
    urls = existing_urls or set()
    image_urls: list[str] = []
    for pattern in (_MARKDOWN_IMAGE_URL_PATTERN, _STRUCTURED_IMAGE_URL_PATTERN, _RAW_IMAGE_URL_PATTERN):
        for match in pattern.findall(answer or ""):
            normalized_url = _clean_output_url(match)
            if normalized_url == "" or normalized_url in urls:
                continue
            urls.add(normalized_url)
            image_urls.append(normalized_url)
    return image_urls


def _extract_inline_image_parts(answer: str, existing_urls: set[str] | None = None) -> list[dict[str, Any]]:
    """从文本答案里兜底识别图片 URL，兼容文生图工具的纯文本返回。"""
    return [_build_output_image_part(url) for url in _extract_inline_image_urls(answer, existing_urls)]


def build_output_parts(answer: str, artifacts: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """根据答案和附件构建统一输出 parts。"""
    normalized_answer = str(answer or "")
    normalized_artifacts = [
        normalized_artifact
        for artifact in (artifacts or [])
        if (normalized_artifact := _normalize_output_artifact(artifact)) is not None
    ]

    parts: list[dict[str, Any]] = []
    if normalized_answer != "":
        parts.append({
            "type": "text",
            "text": normalized_answer,
        })

    image_urls: set[str] = set()
    for artifact in normalized_artifacts:
        if not _is_image_artifact(artifact):
            continue
        image_urls.add(str(artifact.get("url", "")))
        parts.append(
            _build_output_image_part(
                str(artifact.get("url", "")),
                name=str(artifact.get("name", "")),
                mime_type=str(artifact.get("mime_type", "")),
                extension=str(artifact.get("extension", "")),
                group_id=str(artifact.get("group_id", "")),
                group_name=str(artifact.get("group_name", "")),
            )
        )

    parts.extend(_extract_inline_image_parts(normalized_answer, existing_urls=image_urls))

    for artifact in normalized_artifacts:
        if _is_image_artifact(artifact):
            continue
        parts.append(_build_artifact_part(artifact))

    return parts


def build_output_payload(answer: str, agent_thoughts: list[Any] | None = None) -> dict[str, Any]:
    """构建统一的多模态输出载荷。"""
    artifacts = extract_output_artifacts(agent_thoughts)
    return {
        "answer_parts": build_output_parts(answer, artifacts=artifacts),
        "artifacts": artifacts,
    }
