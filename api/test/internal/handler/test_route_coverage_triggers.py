from flask import jsonify


ROUTE_SPECS = [
    {"method": "POST", "url": "/apps/00000000-0000-0000-0000-000000000000/feedbacks", "endpoint": "llmops.create_feedback"},
    {"method": "GET", "url": "/apps/00000000-0000-0000-0000-000000000000/feedbacks", "endpoint": "llmops.get_feedbacks"},
    {"method": "GET", "url": "/apps/00000000-0000-0000-0000-000000000000/evaluations", "endpoint": "llmops.get_evaluations"},
    {"method": "POST", "url": "/apps/00000000-0000-0000-0000-000000000000/evaluations", "endpoint": "llmops.create_evaluation"},
    {"method": "GET", "url": "/apps/00000000-0000-0000-0000-000000000000/evaluations/00000000-0000-0000-0000-000000000000", "endpoint": "llmops.get_evaluation"},
    {"method": "PUT", "url": "/apps/00000000-0000-0000-0000-000000000000/evaluations/00000000-0000-0000-0000-000000000000", "endpoint": "llmops.update_evaluation"},
    {"method": "DELETE", "url": "/apps/00000000-0000-0000-0000-000000000000/evaluations/00000000-0000-0000-0000-000000000000", "endpoint": "llmops.delete_evaluation"},
    {"method": "GET", "url": "/apps/00000000-0000-0000-0000-000000000000/evaluations/00000000-0000-0000-0000-000000000000/cases", "endpoint": "llmops.get_evaluation_cases"},
    {"method": "POST", "url": "/apps/00000000-0000-0000-0000-000000000000/evaluations/00000000-0000-0000-0000-000000000000/cases", "endpoint": "llmops.create_evaluation_case"},
    {"method": "GET", "url": "/assistant-agent/capabilities", "endpoint": "llmops.get_assistant_agent_capabilities"},
    {"method": "GET", "url": "/mcp-providers/categories", "endpoint": "llmops.get_mcp_categories_for_space"},
    {"method": "GET", "url": "/mcp-providers", "endpoint": "llmops.get_mcp_providers_with_page"},
    {"method": "GET", "url": "/mcp-providers/00000000-0000-0000-0000-000000000000", "endpoint": "llmops.get_mcp_provider"},
    {"method": "GET", "url": "/public/mcp-providers/categories", "endpoint": "llmops.get_mcp_categories"},
    {"method": "GET", "url": "/public/mcp-providers", "endpoint": "llmops.get_public_mcp_providers_with_page"},
    {"method": "GET", "url": "/public/mcp-providers/provider-key", "endpoint": "llmops.get_public_mcp_provider"},
    {"method": "GET", "url": "/skills/categories", "endpoint": "llmops.get_skill_categories"},
    {"method": "GET", "url": "/skills", "endpoint": "llmops.get_skills_with_page"},
    {"method": "GET", "url": "/skills/00000000-0000-0000-0000-000000000000", "endpoint": "llmops.get_skill_package"},
    {"method": "GET", "url": "/skills/00000000-0000-0000-0000-000000000000/icon", "endpoint": "llmops.get_skill_package_icon"},
    {"method": "GET", "url": "/skills/00000000-0000-0000-0000-000000000000/versions", "endpoint": "llmops.get_skill_package_versions"},
    {"method": "POST", "url": "/skills/00000000-0000-0000-0000-000000000000/enable", "endpoint": "llmops.enable_skill_package"},
    {"method": "POST", "url": "/skills/00000000-0000-0000-0000-000000000000/disable", "endpoint": "llmops.disable_skill_package"},
    {"method": "POST", "url": "/skills/00000000-0000-0000-0000-000000000000/sync", "endpoint": "llmops.sync_skill_package"},
    {"method": "POST", "url": "/skills/00000000-0000-0000-0000-000000000000/rollback", "endpoint": "llmops.rollback_skill_package"},
    {"method": "POST", "url": "/ai/mcp-schema-chat", "endpoint": "llmops.mcp_schema_assistant_chat"},
    {"method": "POST", "url": "/mcp-providers", "endpoint": "llmops.create_mcp_provider"},
    {"method": "POST", "url": "/mcp-providers/00000000-0000-0000-0000-000000000000", "endpoint": "llmops.update_mcp_provider"},
    {"method": "POST", "url": "/mcp-providers/00000000-0000-0000-0000-000000000000/delete", "endpoint": "llmops.delete_mcp_provider"},
    {"method": "POST", "url": "/mcp-providers/00000000-0000-0000-0000-000000000000/publish", "endpoint": "llmops.publish_mcp_provider"},
    {"method": "POST", "url": "/mcp-providers/00000000-0000-0000-0000-000000000000/regenerate-icon", "endpoint": "llmops.mcp_provider_regenerate_icon"},
    {"method": "POST", "url": "/mcp-providers/00000000-0000-0000-0000-000000000000/unpublish", "endpoint": "llmops.unpublish_mcp_provider"},
    {"method": "POST", "url": "/mcp-providers/generate-icon-preview", "endpoint": "llmops.mcp_provider_generate_icon_preview"},
]


def _stub_view(**_kwargs):
    return jsonify({"ok": True})


def test_trigger_missing_routes_should_return_success(app, monkeypatch):
    with app.test_client() as client:
        for spec in ROUTE_SPECS:
            monkeypatch.setitem(app.view_functions, spec["endpoint"], _stub_view)
            response = client.open(spec["url"], method=spec["method"])
            assert response.status_code == 200
