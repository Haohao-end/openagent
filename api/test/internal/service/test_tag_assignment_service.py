from types import SimpleNamespace
from unittest.mock import patch

import pytest

from internal.service import tag_assignment_service
from internal.service.tag_assignment_service import TagAssignmentService


@pytest.mark.parametrize(
    ("raw_tags", "expected"),
    [
        ("coding", []),
        (["not-a-tag"], []),
        (["coding", "not-a-tag"], ["coding"]),
    ],
)
def test_assign_tags_by_deepseek_rejects_invalid_provider_tags(raw_tags, expected):
    response = SimpleNamespace(
        tool_calls=[{"name": "assign_tags", "args": {"tags": raw_tags}}]
    )

    with patch.object(tag_assignment_service, "Chat") as chat_class:
        chat_class.return_value.invoke.return_value = response
        tags = TagAssignmentService.assign_tags_by_deepseek("name", "description")

    assert tags == expected


def test_assign_tags_by_deepseek_should_redact_provider_exception(caplog):
    secret = "SYNTHETIC_PROVIDER_CREDENTIAL"
    with patch.object(tag_assignment_service, "Chat") as chat_class:
        chat_class.return_value.invoke.side_effect = RuntimeError(
            f"provider credential={secret}"
        )

        result = TagAssignmentService.assign_tags_by_deepseek(
            "private-agent-name", f"description containing {secret}"
        )

    assert result == []
    assert secret not in caplog.text
    assert "error_type=RuntimeError" in caplog.text


def test_match_tags_by_keywords_handles_none_and_empty_inputs():
    assert TagAssignmentService.match_tags_by_keywords(None, None) == []
    assert TagAssignmentService.match_tags_by_keywords("", "") == []
    assert TagAssignmentService.match_tags_by_keywords("   ", "   ") == []

    # Keyword match with None description
    tags_coding = TagAssignmentService.match_tags_by_keywords("Python代码助手", None)
    assert "coding" in tags_coding

    # Keyword match with None name
    tags_writing = TagAssignmentService.match_tags_by_keywords(None, "帮助用户撰写文案与文章")
    assert "writing" in tags_writing


def test_auto_assign_tags_falls_back_safely_on_none_inputs():
    with patch.object(TagAssignmentService, "assign_tags_by_deepseek", return_value=[]):
        tags = TagAssignmentService.auto_assign_tags(None, None)
    assert tags == ["other"]
