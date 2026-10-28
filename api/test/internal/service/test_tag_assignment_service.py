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
