from __future__ import annotations

import pytest
from internal.core.skills.skill_catalog import SkillCatalogManager


def test_skill_catalog_manager_should_load_skill_md_as_readme(tmp_path):
    catalog_root = tmp_path / "catalog"
    package_dir = catalog_root / "demo_skill"
    package_dir.mkdir(parents=True)

    (package_dir / "manifest.yaml").write_text(
        "\n".join(
            [
                "source_key: demo_skill",
                "name: 演示技能",
                "label: 演示技能",
                "description: 技能描述",
                "category: 测试",
                "executor_type: scf",
                "version: 1",
                "tools: []",
            ]
        ),
        encoding="utf-8",
    )
    (package_dir / "skill.py").write_text("def run(params):\n    return params\n", encoding="utf-8")
    (package_dir / "skill.md").write_text("# 演示技能\n\n这是技能正文。", encoding="utf-8")

    manager = SkillCatalogManager(catalog_root=str(catalog_root))
    packages = manager.list_packages()

    assert len(packages) == 1
    assert packages[0].source_key == "demo_skill"
    assert packages[0].enabled is True
    assert packages[0].readme == "# 演示技能\n\n这是技能正文。"
    assert packages[0].bundle["skill.md"] == "# 演示技能\n\n这是技能正文。"


def test_skill_catalog_manager_should_strip_tools_from_prompt_only_packages(tmp_path):
    catalog_root = tmp_path / "catalog"
    package_dir = catalog_root / "prompt_skill"
    package_dir.mkdir(parents=True)

    (package_dir / "manifest.yaml").write_text(
        "\n".join(
            [
                "source_key: prompt_skill",
                "name: 提示词技能",
                "label: 提示词技能",
                "description: 仅保留提示词",
                "category: 测试",
                "executor_type: prompt",
                "version: 1",
                "tools:",
                "  - name: demo_tool",
                "    label: 演示工具",
                "    description: 不应暴露",
                "    entrypoint: demo_tool",
                "    input_schema:",
                "      type: object",
            ]
        ),
        encoding="utf-8",
    )
    (package_dir / "skill.md").write_text("# 提示词技能\n\n这是提示词正文。", encoding="utf-8")

    manager = SkillCatalogManager(catalog_root=str(catalog_root))
    packages = manager.list_packages()

    assert len(packages) == 1
    assert packages[0].source_key == "prompt_skill"
    assert packages[0].tools == []


@pytest.mark.parametrize(
    ("enabled_value", "expected"),
    [
        ("false", False),
        ('"false"', False),
        ('"true"', True),
        ("null", False),
        ("1", False),
        ("[]", False),
        ("{}", False),
    ],
)
def test_skill_catalog_manager_should_parse_enabled_strings_and_fail_closed_on_invalid_types(
    tmp_path, enabled_value, expected
):
    package_dir = tmp_path / "catalog" / "demo_skill"
    package_dir.mkdir(parents=True)
    (package_dir / "manifest.yaml").write_text(
        f"source_key: demo_skill\nenabled: {enabled_value}\n", encoding="utf-8"
    )

    packages = SkillCatalogManager(catalog_root=str(package_dir.parent)).list_packages()

    assert len(packages) == 1
    assert packages[0].enabled is expected
