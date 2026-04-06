from __future__ import annotations

from uuid import uuid4

import pytest
from wtforms.validators import ValidationError

from internal.schema.api_tool_schema import (
    CreateApiToolReq,
    GetApiToolProviderResp,
    GetApiToolProvidersWithPageReq,
    GetApiToolProvidersWithPageResp,
    GetApiToolResp,
    UpdateApiToolProviderReq,
    ValidateOpenAPISchemaReq,
)
from internal.schema.workflow_schema import (
    CreateWorkflowReq,
    GetWorkflowResp,
    GetWorkflowsWithPageReq,
    GetWorkflowsWithPageResp,
    UpdateWorkflowReq,
)
from test.internal.schema.utils import ns, utc_dt


def _validate_form(form_request, form_cls, *, data=None, json=None, content_type=None):
    with form_request(data=data, json=json, content_type=content_type):
        form = form_cls(meta={"csrf": False})
        return form.validate(), form


def test_validate_openapi_schema_req_should_require_payload(form_request):
    ok, form = _validate_form(form_request, ValidateOpenAPISchemaReq, data={"openapi_schema": "{}"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, ValidateOpenAPISchemaReq, data={"openapi_schema": ""})
    assert not ok
    assert "openapi_schema" in form.errors


def test_api_tool_provider_page_req_should_allow_optional_search_word(form_request):
    ok, form = _validate_form(form_request, GetApiToolProvidersWithPageReq, data={"search_word": "tool"})
    assert ok, form.errors


def test_create_and_update_api_tool_forms_should_validate_required_fields(form_request):
    ok, form = _validate_form(
        form_request,
        CreateApiToolReq,
        data={
            "name": "provider",
            "icon": "https://img.example.com/provider.png",
            "openapi_schema": "{}",
        },
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        UpdateApiToolProviderReq,
        data={
            "name": "x" * 31,
            "icon": "bad-url",
            "openapi_schema": "",
        },
    )
    assert not ok
    assert "name" in form.errors
    assert "icon" in form.errors
    assert "openapi_schema" in form.errors


def test_api_tool_header_validator_should_enforce_dict_and_exact_keys(form_request):
    with form_request():
        create_form = CreateApiToolReq(meta={"csrf": False})
        create_form.headers.data = [{"key": "Authorization", "value": "Bearer token"}]
        CreateApiToolReq.validate_headers(create_form, create_form.headers)

        create_form.headers.data = ["bad"]  # type: ignore[list-item]
        with pytest.raises(ValidationError, match="headers里的每一格元素都必须是字典"):
            CreateApiToolReq.validate_headers(create_form, create_form.headers)

        create_form.headers.data = [{"key": "Authorization", "value": "Bearer token", "extra": 1}]
        with pytest.raises(ValidationError, match="headers里的每一格元素都必须包含key和value两个属性"):
            CreateApiToolReq.validate_headers(create_form, create_form.headers)

        update_form = UpdateApiToolProviderReq(meta={"csrf": False})
        update_form.headers.data = [{"key": "k", "value": "v"}]
        UpdateApiToolProviderReq.validate_headers(update_form, update_form.headers)

        update_form.headers.data = ["bad"]  # type: ignore[list-item]
        with pytest.raises(ValidationError, match="headers里的每一格元素都必须是字典"):
            UpdateApiToolProviderReq.validate_headers(update_form, update_form.headers)

        update_form.headers.data = [{"key": "k", "value": "v", "extra": 1}]
        with pytest.raises(ValidationError, match="headers里的每一格元素都必须包含key和value两个属性"):
            UpdateApiToolProviderReq.validate_headers(update_form, update_form.headers)


def test_api_tool_response_schemas_should_strip_internal_parameter_fields():
    provider = ns(
        id=uuid4(),
        name="provider",
        icon="https://img.example.com/provider.png",
        openapi_schema='{"openapi":"3.0.0"}',
        description="provider-desc",
        headers=[{"key": "Authorization", "value": "token"}],
        account=ns(name="creator", avatar="https://img.example.com/avatar.png"),
        updated_at=utc_dt(2024, 1, 2, 0, 0, 0),
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
        tools=[],
    )
    provider_payload = GetApiToolProviderResp().dump(provider)
    assert provider_payload["name"] == "provider"
    assert provider_payload["headers"][0]["key"] == "Authorization"

    tool = ns(
        id=uuid4(),
        name="tool",
        description="tool-desc",
        parameters=[
            {"name": "query", "in": "query", "type": "string"},
            {"name": "body", "in": "body", "type": "object"},
        ],
        provider=provider,
    )
    tool_payload = GetApiToolResp().dump(tool)
    assert all("in" not in item for item in tool_payload["inputs"])
    assert tool_payload["provider"]["name"] == "provider"

    provider_with_tools = ns(
        id=provider.id,
        name=provider.name,
        icon=provider.icon,
        openapi_schema=provider.openapi_schema,
        description=provider.description,
        headers=provider.headers,
        account=provider.account,
        updated_at=provider.updated_at,
        created_at=provider.created_at,
        tools=[tool],
    )
    provider_page_payload = GetApiToolProvidersWithPageResp().dump(provider_with_tools)
    assert provider_page_payload["tools"][0]["name"] == "tool"
    assert all("in" not in item for item in provider_page_payload["tools"][0]["inputs"])
    assert provider_page_payload["creator_name"] == "creator"
    assert provider_page_payload["creator_avatar"] == "https://img.example.com/avatar.png"


def test_workflow_forms_should_validate_pattern_and_description(form_request):
    ok, form = _validate_form(
        form_request,
        CreateWorkflowReq,
        data={
            "name": "工作流",
            "tool_call_name": "workflow_tool_1",
            "icon": "https://img.example.com/workflow.png",
            "description": "desc",
        },
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        CreateWorkflowReq,
        data={
            "name": "工作流",
            "tool_call_name": "1invalid",
            "icon": "https://img.example.com/workflow.png",
            "description": "desc",
        },
    )
    assert not ok
    assert "tool_call_name" in form.errors

    ok, form = _validate_form(
        form_request,
        UpdateWorkflowReq,
        data={
            "name": "工作流",
            "tool_call_name": "workflow_tool_1",
            "icon": "https://img.example.com/workflow.png",
            "description": "x" * 1025,
        },
    )
    assert not ok
    assert "description" in form.errors


def test_workflow_response_schemas_should_count_nodes_from_expected_graph():
    workflow = ns(
        id=uuid4(),
        name="workflow",
        tool_call_name="workflow_tool_1",
        icon="https://img.example.com/workflow.png",
        description="desc",
        status="draft",
        is_debug_passed=False,
        is_public=False,
        draft_graph={"nodes": [{}, {}, {}]},
        graph={"nodes": [{}, {}]},
        account=ns(name="workflow-owner", avatar="https://img.example.com/workflow-owner.png"),
        published_at=utc_dt(2024, 1, 3, 0, 0, 0),
        updated_at=utc_dt(2024, 1, 2, 0, 0, 0),
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )
    detail = GetWorkflowResp().dump(workflow)
    listing = GetWorkflowsWithPageResp().dump(workflow)
    assert detail["node_count"] == 3
    assert listing["node_count"] == 3
    assert listing["creator_name"] == "workflow-owner"
    assert listing["creator_avatar"] == "https://img.example.com/workflow-owner.png"


def test_workflows_with_page_req_should_validate_status_enum(form_request):
    ok, form = _validate_form(form_request, GetWorkflowsWithPageReq, data={"status": "draft"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, GetWorkflowsWithPageReq, data={"status": "bad"})
    assert not ok
    assert "status" in form.errors
