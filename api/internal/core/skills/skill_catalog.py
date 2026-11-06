from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from internal.lib.helper import generate_text_hash

logger = logging.getLogger(__name__)

_TEXT_FILE_SUFFIXES = {
    ".py",
    ".yaml",
    ".yml",
    ".json",
    ".md",
    ".txt",
    ".toml",
    ".ini",
    ".cfg",
    ".svg",
}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    return False


def _normalize_int(value: Any, default: int = 1) -> int:
    try:
        normalized = int(value)
    except Exception:
        return default
    return normalized if normalized > 0 else default


@dataclass(slots=True)
class SkillToolDefinition:
    """技能包公开的单个工具定义。"""

    name: str
    label: str
    description: str
    entrypoint: str
    input_schema: dict[str, Any]


@dataclass(slots=True)
class LocalSkillPackage:
    """本地技能包目录解析结果。"""

    source_key: str
    name: str
    label: str
    description: str
    readme: str
    category: str
    tags: list[str]
    icon: str
    enabled: bool
    version: int
    executor_type: str
    capabilities: dict[str, Any]
    tools: list[SkillToolDefinition]
    source_path: str
    manifest: dict[str, Any]
    bundle: dict[str, str]
    checksum: str


class SkillCatalogManager:
    """本地技能包目录管理器。

    目录结构示例：
    catalog/
      code_workbench/
        manifest.yaml
        skill.md
        skill.py
        icon.svg
    """

    def __init__(self, catalog_root: str | None = None) -> None:
        self.catalog_root = Path(catalog_root) if catalog_root else Path(__file__).resolve().parent / "catalog"
        self._packages_cache: dict[str, LocalSkillPackage] | None = None

    def clear_cache(self) -> None:
        self._packages_cache = None

    def list_packages(self) -> list[LocalSkillPackage]:
        if self._packages_cache is None:
            self._packages_cache = self._load_packages()
        return list(self._packages_cache.values())

    def get_package(self, source_key: str) -> LocalSkillPackage | None:
        normalized_source_key = _normalize_text(source_key)
        if not normalized_source_key:
            return None
        packages = self.list_packages()
        for package in packages:
            if package.source_key == normalized_source_key:
                return package
        return None

    def get_package_bundle(self, source_key: str) -> dict[str, str]:
        package = self.get_package(source_key)
        return package.bundle if package else {}

    def read_file(self, source_key: str, relative_path: str) -> tuple[bytes | None, str | None, str | None]:
        package = self.get_package(source_key)
        if not package:
            return None, None, None

        normalized_path = _normalize_text(relative_path)
        if not normalized_path:
            return None, None, None

        file_path = Path(package.source_path) / normalized_path
        if not file_path.exists() or not file_path.is_file():
            return None, None, None

        if file_path.suffix.lower() not in _TEXT_FILE_SUFFIXES:
            try:
                return file_path.read_bytes(), "application/octet-stream", None
            except Exception:
                return None, None, None

        try:
            content = file_path.read_bytes()
        except Exception:
            return None, None, None

        mimetype = "image/svg+xml" if file_path.suffix.lower() == ".svg" else "text/plain; charset=utf-8"
        return content, mimetype, None

    def _load_packages(self) -> dict[str, LocalSkillPackage]:
        packages: dict[str, LocalSkillPackage] = {}
        if not self.catalog_root.exists():
            return packages

        for manifest_path in sorted(self.catalog_root.glob("*/manifest.yaml")):
            try:
                package = self._load_single_package(manifest_path.parent)
                if package:
                    packages[package.source_key] = package
            except Exception as exc:
                logger.exception("加载技能包失败: %s", exc)
        return packages

    def _load_single_package(self, package_path: Path) -> LocalSkillPackage | None:
        manifest_path = package_path / "manifest.yaml"
        if not manifest_path.exists():
            return None

        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = yaml.safe_load(manifest_text) or {}
        if not isinstance(manifest, dict):
            return None

        source_key = _normalize_text(manifest.get("source_key") or package_path.name)
        if not source_key:
            return None

        version = _normalize_int(manifest.get("version", 1), 1)
        enabled = _normalize_bool(manifest.get("enabled", True))
        name = _normalize_text(manifest.get("name") or source_key)
        label = _normalize_text(manifest.get("label") or name)
        description = _normalize_text(manifest.get("description"))
        readme = self._read_package_readme(package_path)
        category = _normalize_text(manifest.get("category") or "通用")
        icon = _normalize_text(manifest.get("icon") or "")
        executor_type = _normalize_text(manifest.get("executor_type") or "scf") or "scf"
        tags = [str(tag).strip() for tag in (manifest.get("tags") or []) if str(tag).strip()]
        capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), dict) else {}
        tools = self._normalize_tool_definitions(manifest.get("tools"))
        if executor_type.lower() != "scf":
            tools = []

        bundle: dict[str, str] = {"manifest.yaml": manifest_text}
        for file_path in sorted(package_path.rglob("*")):
            if file_path.is_dir():
                continue
            if file_path.name == "manifest.yaml":
                continue
            if file_path.suffix.lower() not in _TEXT_FILE_SUFFIXES:
                continue
            try:
                bundle[file_path.relative_to(package_path).as_posix()] = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                logger.warning("跳过非 UTF-8 技能包文件: %s", file_path)
            except Exception as exc:
                logger.exception("读取技能包文件失败: %s", exc)

        checksum = generate_text_hash(
            json.dumps(
                {
                    "manifest": manifest,
                    "bundle": bundle,
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        )

        return LocalSkillPackage(
            source_key=source_key,
            name=name,
            label=label,
            description=description,
            readme=readme,
            category=category,
            tags=tags,
            icon=icon,
            enabled=enabled,
            version=version,
            executor_type=executor_type,
            capabilities=capabilities,
            tools=tools,
            source_path=str(package_path.resolve()),
            manifest=manifest,
            bundle=bundle,
            checksum=checksum,
        )

    def _read_package_readme(self, package_path: Path) -> str:
        for markdown_name in ("skill.md", "README.md", "readme.md"):
            markdown_path = package_path / markdown_name
            if not markdown_path.exists() or not markdown_path.is_file():
                continue
            try:
                return markdown_path.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError:
                logger.warning("跳过非 UTF-8 技能正文文件: %s", markdown_path)
            except Exception as exc:
                logger.exception("读取技能正文失败: %s", exc)
        return ""

    def _normalize_tool_definitions(self, raw_tools: Any) -> list[SkillToolDefinition]:
        if not isinstance(raw_tools, list):
            return []

        normalized_tools: list[SkillToolDefinition] = []
        for tool in raw_tools:
            if not isinstance(tool, dict):
                continue

            name = _normalize_text(tool.get("name"))
            if not name:
                continue

            label = _normalize_text(tool.get("label") or tool.get("title") or name)
            description = _normalize_text(tool.get("description"))
            entrypoint = _normalize_text(tool.get("entrypoint") or tool.get("function") or name) or name
            input_schema = tool.get("input_schema") or tool.get("inputSchema") or {}
            if not isinstance(input_schema, dict):
                input_schema = {}

            normalized_tools.append(
                SkillToolDefinition(
                    name=name,
                    label=label,
                    description=description,
                    entrypoint=entrypoint,
                    input_schema=input_schema,
                )
            )

        return normalized_tools
