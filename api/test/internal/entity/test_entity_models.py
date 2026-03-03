from __future__ import annotations

import pytest
from pydantic import ValidationError

from internal.entity.conversation_entity import ConversationInfo, SuggestedQuestions


def test_conversation_info_should_validate_required_fields():
    payload = ConversationInfo(
        language_type="中英混合",
        reasoning="输入包含中文和英文专业术语",
        subject="OpenAI 接口调用排错",
    )
    assert payload.language_type == "中英混合"
    assert payload.reasoning
    assert payload.subject == "OpenAI 接口调用排错"


def test_conversation_info_should_raise_when_required_field_missing():
    with pytest.raises(ValidationError):
        ConversationInfo(
            language_type="中文",
            reasoning="用户输入为中文",
            # 缺少 subject
        )


def test_suggested_questions_should_accept_string_list():
    payload = SuggestedQuestions(questions=["如何配置回调？", "如何查看错误日志？", "如何做重试机制？"])
    assert len(payload.questions) == 3
    assert all(isinstance(item, str) for item in payload.questions)


def test_suggested_questions_should_reject_non_list_type():
    with pytest.raises(ValidationError):
        SuggestedQuestions(questions="这不是列表")  # type: ignore[arg-type]


def test_suggested_questions_should_reject_non_string_items():
    with pytest.raises(ValidationError):
        SuggestedQuestions(questions=["ok", 1, "still-ok"])  # type: ignore[list-item]

