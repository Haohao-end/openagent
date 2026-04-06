from __future__ import annotations

from uuid import uuid4

import pytest
from wtforms.validators import ValidationError

from internal.entity.dataset_entity import DEFAULT_PROCESS_RULE, ProcessType
from internal.schema.dataset_schema import (
    CreateDatasetReq,
    GetDatasetQueriesResp,
    GetDatasetResp,
    GetDatasetsWithPageResp,
    HitReq,
    UpdateDatasetReq,
)
from internal.schema.document_schema import (
    CreateDocumentsReq,
    CreateDocumentsResp,
    GetDocumentResp,
    GetDocumentsWithPageResp,
    GetDocumentsWithPageReq,
    UpdateDocumentEnabledReq,
    UpdateDocumentNameReq,
)
from internal.schema.segment_schema import (
    CreateSegmentReq,
    GetSegmentResp,
    GetSegmentsWithPageResp,
    GetSegmentsWithPageReq,
    UpdateSegmentEnabledReq,
    UpdateSegmentReq,
    _get_keywords_from_json,
)
from test.internal.schema.utils import ns, utc_dt


def _validate_form(form_request, form_cls, *, data=None, json=None, content_type=None):
    with form_request(data=data, json=json, content_type=content_type):
        form = form_cls(meta={"csrf": False})
        return form.validate(), form


def _valid_custom_rule() -> dict:
    return {
        "pre_process_rules": [
            {"id": "remove_extra_space", "enabled": True},
            {"id": "remove_url_and_email", "enabled": False},
        ],
        "segment": {
            "separators": ["\n\n", "\n", " "],
            "chunk_size": 200,
            "chunk_overlap": 50,
        },
        "ignored": "will be removed",
    }


def test_dataset_forms_should_validate_normal_and_boundary_values(form_request):
    ok, form = _validate_form(
        form_request,
        CreateDatasetReq,
        data={
            "name": "知识库",
            "icon": "https://img.example.com/dataset.png",
            "description": "desc",
        },
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        CreateDatasetReq,
        data={
            "name": "知识库",
            "icon": "https://img.example.com/dataset.png",
            "description": "x" * 2001,
        },
    )
    assert not ok
    assert "description" in form.errors

    ok, form = _validate_form(
        form_request,
        UpdateDatasetReq,
        data={
            "name": "知识库",
            "icon": "https://img.example.com/dataset.png",
            "description": "",
        },
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        HitReq,
        data={
            "query": "hello",
            "retrieval_strategy": "semantic",
            "k": "10",
            "score": "0.99",
        },
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        HitReq,
        data={
            "query": "hello",
            "retrieval_strategy": "invalid",
            "k": "0",
            "score": "1",
        },
    )
    assert not ok
    assert "retrieval_strategy" in form.errors
    assert "k" in form.errors
    assert "score" in form.errors


def test_dataset_response_schema_should_dump_expected_fields():
    dataset = ns(
        id=uuid4(),
        name="知识库",
        icon="https://img.example.com/dataset.png",
        description="desc",
        document_count=2,
        hit_count=10,
        related_app_count=3,
        character_count=1234,
        account=ns(name="dataset-owner", avatar="https://img.example.com/dataset-owner.png"),
        updated_at=utc_dt(2024, 1, 2, 0, 0, 0),
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )
    detail = GetDatasetResp().dump(dataset)
    listing = GetDatasetsWithPageResp().dump(dataset)

    assert detail["hit_count"] == 10
    assert detail["upload_at"] == int(utc_dt(2024, 1, 2, 0, 0, 0).timestamp())
    assert listing["related_app_count"] == 3
    assert listing["creator_name"] == "dataset-owner"
    assert listing["creator_avatar"] == "https://img.example.com/dataset-owner.png"

    query = ns(
        id=uuid4(),
        dataset_id=uuid4(),
        query="q",
        source="app",
        created_at=utc_dt(2024, 1, 1, 12, 0, 0),
    )
    query_payload = GetDatasetQueriesResp().dump(query)
    assert query_payload["query"] == "q"
    assert query_payload["source"] == "app"


def test_document_base_forms_should_validate(form_request):
    ok, form = _validate_form(form_request, GetDocumentsWithPageReq, data={"search_word": "doc"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, UpdateDocumentNameReq, data={"name": "a" * 100})
    assert ok, form.errors

    ok, form = _validate_form(form_request, UpdateDocumentNameReq, data={"name": "a" * 101})
    assert not ok
    assert "name" in form.errors

    with form_request():
        form = UpdateDocumentEnabledReq(meta={"csrf": False})
        form.enabled.data = "bad-bool"
        with pytest.raises(ValidationError, match="enabled状态不能为空且必须为布尔值"):
            form.validate_enabled(form.enabled)

        form.enabled.data = True
        assert form.validate_enabled(form.enabled) is None


def test_validate_upload_file_ids_should_cover_type_count_uuid_and_dedup(form_request):
    with form_request():
        form = CreateDocumentsReq(meta={"csrf": False})

        form.upload_file_ids.data = "bad-type"
        with pytest.raises(ValidationError, match="文件id列表格式必须是数组"):
            form.validate_upload_file_ids(form.upload_file_ids)

        form.upload_file_ids.data = []
        with pytest.raises(ValidationError, match="新增的文档数范围在0-10"):
            form.validate_upload_file_ids(form.upload_file_ids)

        form.upload_file_ids.data = [str(uuid4()) for _ in range(11)]
        with pytest.raises(ValidationError, match="新增的文档数范围在0-10"):
            form.validate_upload_file_ids(form.upload_file_ids)

        form.upload_file_ids.data = ["not-uuid"]
        with pytest.raises(ValidationError, match="文件id的格式必须是UUID"):
            form.validate_upload_file_ids(form.upload_file_ids)

        duplicate_id = str(uuid4())
        other_id = str(uuid4())
        form.upload_file_ids.data = [duplicate_id, duplicate_id, other_id]
        form.validate_upload_file_ids(form.upload_file_ids)
        assert form.upload_file_ids.data == [duplicate_id, other_id]
        assert len(form.upload_file_ids.data) == 2


def test_validate_rule_should_set_default_when_process_type_is_automatic(form_request):
    with form_request():
        form = CreateDocumentsReq(meta={"csrf": False})
        form.process_type.data = ProcessType.AUTOMATIC.value
        form.rule.data = {"ignored": True}

        form.validate_rule(form.rule)
        assert form.rule.data == DEFAULT_PROCESS_RULE["rule"]


@pytest.mark.parametrize(
    ("rule_payload", "expected_error"),
    [
        (None, "自定义处理模式下，rule不能为空"),
        ({}, "自定义处理模式下，rule不能为空"),
        ({"pre_process_rules": "bad"}, "pre_process_rules必须为列表"),
        (
            {"pre_process_rules": [{"id": "bad-id", "enabled": True}], "segment": {"separators": ["\n"], "chunk_size": 200, "chunk_overlap": 50}},
            "预处理id格式错误",
        ),
        (
            {"pre_process_rules": [{"id": "remove_extra_space", "enabled": "yes"}], "segment": {"separators": ["\n"], "chunk_size": 200, "chunk_overlap": 50}},
            "预处理enabled格式错误",
        ),
        (
            {"pre_process_rules": [{"id": "remove_extra_space", "enabled": True}, {"id": "remove_extra_space", "enabled": False}], "segment": {"separators": ["\n"], "chunk_size": 200, "chunk_overlap": 50}},
            "预处理规则格式错误，请重试尝试",
        ),
        (
            {"pre_process_rules": [{"id": "remove_extra_space", "enabled": True}, {"id": "remove_url_and_email", "enabled": False}]},
            "分段设置不能为空且为字典",
        ),
    ],
)
def test_validate_rule_should_raise_for_invalid_custom_configs(form_request, rule_payload, expected_error):
    with form_request():
        form = CreateDocumentsReq(meta={"csrf": False})
        form.process_type.data = ProcessType.CUSTOM.value
        form.rule.data = rule_payload
        with pytest.raises(ValidationError, match=expected_error):
            form.validate_rule(form.rule)


def test_validate_rule_should_validate_segment_config_boundaries(form_request):
    # 该用例集中覆盖 segment 结构下的关键边界分支，确保错误定位精确。
    with form_request():
        form = CreateDocumentsReq(meta={"csrf": False})
        form.process_type.data = ProcessType.CUSTOM.value

        bad_separators_rule = _valid_custom_rule()
        bad_separators_rule["segment"]["separators"] = "bad"  # type: ignore[index]
        form.rule.data = bad_separators_rule
        with pytest.raises(ValidationError, match="分隔符列表不能为空且为列表"):
            form.validate_rule(form.rule)

        bad_separator_item_rule = _valid_custom_rule()
        bad_separator_item_rule["segment"]["separators"] = ["\n", 1]  # type: ignore[index]
        form.rule.data = bad_separator_item_rule
        with pytest.raises(ValidationError, match="分隔符列表元素类型错误"):
            form.validate_rule(form.rule)

        empty_separator_rule = _valid_custom_rule()
        empty_separator_rule["segment"]["separators"] = []
        form.rule.data = empty_separator_rule
        with pytest.raises(ValidationError, match="分隔符列表不能为空列表"):
            form.validate_rule(form.rule)

        non_int_chunk_rule = _valid_custom_rule()
        non_int_chunk_rule["segment"]["chunk_size"] = "200"  # type: ignore[index]
        form.rule.data = non_int_chunk_rule
        with pytest.raises(ValidationError, match="分割块大小不能为空且为整数"):
            form.validate_rule(form.rule)

        range_chunk_rule = _valid_custom_rule()
        range_chunk_rule["segment"]["chunk_size"] = 99
        form.rule.data = range_chunk_rule
        with pytest.raises(ValidationError, match="分割块大小在100-1000"):
            form.validate_rule(form.rule)

        non_int_overlap_rule = _valid_custom_rule()
        non_int_overlap_rule["segment"]["chunk_overlap"] = "10"  # type: ignore[index]
        form.rule.data = non_int_overlap_rule
        with pytest.raises(ValidationError, match="块重叠大小不能为空且为整数"):
            form.validate_rule(form.rule)

        range_overlap_rule = _valid_custom_rule()
        range_overlap_rule["segment"]["chunk_overlap"] = 101
        form.rule.data = range_overlap_rule
        with pytest.raises(ValidationError, match="块重叠大小在0-100"):
            form.validate_rule(form.rule)


def test_validate_rule_should_normalize_custom_rule_and_strip_extra_fields(form_request):
    with form_request():
        form = CreateDocumentsReq(meta={"csrf": False})
        form.process_type.data = ProcessType.CUSTOM.value
        rule = _valid_custom_rule()
        form.rule.data = rule

        form.validate_rule(form.rule)

        # 1.预处理规则被限制为两种且去掉无关字段
        assert {item["id"] for item in form.rule.data["pre_process_rules"]} == {
            "remove_extra_space",
            "remove_url_and_email",
        }
        # 2.外部多余字段会被剔除，最终只保留规范化后的结构
        assert set(form.rule.data.keys()) == {"pre_process_rules", "segment"}
        assert form.rule.data["segment"]["chunk_size"] == 200


def test_document_response_schema_should_dump_expected_fields():
    document = ns(
        id=uuid4(),
        dataset_id=uuid4(),
        name="doc-1",
        segment_count=3,
        character_count=100,
        hit_count=2,
        position=1,
        enabled=True,
        disabled_at=None,
        status="completed",
        error="",
        updated_at=utc_dt(2024, 1, 2, 0, 0, 0),
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )
    detail = GetDocumentResp().dump(document)
    listing = GetDocumentsWithPageResp().dump(document)
    assert detail["name"] == "doc-1"
    assert detail["disabled_at"] == 0
    assert listing["enabled"] is True

    batch = CreateDocumentsResp().dump(([document], "batch-1"))
    assert batch["batch"] == "batch-1"
    assert batch["documents"][0]["status"] == "completed"


def test_get_keywords_from_json_should_handle_non_dict_and_missing_key(form_request):
    with form_request(json=["not-dict"]):
        assert _get_keywords_from_json() == []

    with form_request(json={"other": 1}):
        assert _get_keywords_from_json() == []

    with form_request(json={"keywords": ["a", "b"]}):
        assert _get_keywords_from_json() == ["a", "b"]


def test_segment_base_forms_should_validate(form_request):
    ok, form = _validate_form(form_request, GetSegmentsWithPageReq, data={"search_word": "seg"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, CreateSegmentReq, data={"content": "text"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, CreateSegmentReq, data={"content": ""})
    assert not ok
    assert "content" in form.errors

    ok, form = _validate_form(form_request, UpdateSegmentReq, data={"content": "text"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, UpdateSegmentReq, data={"content": ""})
    assert not ok
    assert "content" in form.errors

    with form_request():
        form = UpdateSegmentEnabledReq(meta={"csrf": False})
        form.enabled.data = "bad-bool"
        with pytest.raises(ValidationError, match="enabled状态不能为空且必须为布尔值"):
            form.validate_enabled(form.enabled)

        form.enabled.data = False
        assert form.validate_enabled(form.enabled) is None


def test_create_segment_validate_keywords_should_cover_none_type_count_and_dedup(form_request):
    # 这里显式使用 JSON 请求体，验证 _get_keywords_from_json 的“原始值读取”逻辑，
    # 防止字符串被 ListField 包装成 list 后绕过类型检查。
    with form_request(json={"keywords": None}):
        form = CreateSegmentReq(meta={"csrf": False})
        form.validate_keywords(form.keywords)
        assert form.keywords.data == []

    with form_request(json={"keywords": "bad"}):
        form = CreateSegmentReq(meta={"csrf": False})
        with pytest.raises(ValidationError, match="关键词列表格式必须是数组"):
            form.validate_keywords(form.keywords)

    with form_request(json={"keywords": [str(i) for i in range(11)]}):
        form = CreateSegmentReq(meta={"csrf": False})
        with pytest.raises(ValidationError, match="关键词长度范围数量在1~10"):
            form.validate_keywords(form.keywords)

    with form_request(json={"keywords": ["ok", 1]}):
        form = CreateSegmentReq(meta={"csrf": False})
        with pytest.raises(ValidationError, match="关键词必须是字符串"):
            form.validate_keywords(form.keywords)

    with form_request(json={"keywords": ["a", "a", "b"]}):
        form = CreateSegmentReq(meta={"csrf": False})
        form.validate_keywords(form.keywords)
        assert form.keywords.data == ["a", "b"]


def test_update_segment_validate_keywords_should_cover_length_error_and_dedup(form_request):
    with form_request(json={"keywords": None}):
        form = UpdateSegmentReq(meta={"csrf": False})
        form.validate_keywords(form.keywords)
        assert form.keywords.data == []

    with form_request(json={"keywords": "bad"}):
        form = UpdateSegmentReq(meta={"csrf": False})
        with pytest.raises(ValidationError, match="关键词列表格式必须是数组"):
            form.validate_keywords(form.keywords)

    with form_request(json={"keywords": [str(i) for i in range(11)]}):
        form = UpdateSegmentReq(meta={"csrf": False})
        with pytest.raises(ValidationError, match="关键词长度范围数量在1-10"):
            form.validate_keywords(form.keywords)

    with form_request(json={"keywords": ["ok", 1]}):
        form = UpdateSegmentReq(meta={"csrf": False})
        with pytest.raises(ValidationError, match="关键词必须是字符串"):
            form.validate_keywords(form.keywords)

    with form_request(json={"keywords": ["x", "x", "y"]}):
        form = UpdateSegmentReq(meta={"csrf": False})
        form.validate_keywords(form.keywords)
        assert form.keywords.data == ["x", "y"]


def test_segment_response_schema_should_dump_expected_fields():
    segment = ns(
        id=uuid4(),
        document_id=uuid4(),
        dataset_id=uuid4(),
        position=1,
        content="segment-content",
        keywords=["a", "b"],
        character_count=10,
        token_count=5,
        hit_count=3,
        hash="hash",
        enabled=True,
        disabled_at=None,
        status="completed",
        error="",
        updated_at=utc_dt(2024, 1, 2, 0, 0, 0),
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )
    detail = GetSegmentResp().dump(segment)
    listing = GetSegmentsWithPageResp().dump(segment)
    assert detail["hash"] == "hash"
    assert detail["disabled_at"] == 0
    assert listing["keywords"] == ["a", "b"]
