from __future__ import annotations

from collections import defaultdict


def _methods(rule):
    return {m for m in rule.methods if m not in {"HEAD", "OPTIONS"}}


class TestRouterFullMatrix:
    """路由全量矩阵契约测试，覆盖路径、HTTP 方法与蓝图边界。"""

    def test_should_match_full_path_method_matrix(self, app):
        route_methods = defaultdict(set)
        for rule in app.url_map.iter_rules():
            if rule.endpoint == "static":
                continue
            route_methods[rule.rule].update(_methods(rule))

        expected = {
            '/account': {'GET'},
            '/account/avatar': {'POST'},
            '/account/name': {'POST'},
            '/account/password': {'POST'},
            '/ai/chat': {'POST'},
            '/ai/openapi-schema-chat': {'POST'},
            '/ai/optimize-prompt': {'POST'},
            '/ai/suggested-questions': {'POST'},
            '/analysis/<uuid:app_id>': {'GET'},
            '/api-tools': {'GET', 'POST'},
            '/api-tools/<uuid:provider_id>': {'GET', 'POST'},
            '/api-tools/<uuid:provider_id>/delete': {'POST'},
            '/api-tools/<uuid:provider_id>/regenerate-icon': {'POST'},
            '/api-tools/<uuid:provider_id>/tools/<string:tool_name>': {'GET'},
            '/api-tools/generate-icon-preview': {'POST'},
            '/api-tools/validate-openapi-schema': {'POST'},
            '/apps': {'GET', 'POST'},
            '/apps/<uuid:app_id>': {'GET', 'POST'},
            '/apps/<uuid:app_id>/cancel-publish': {'POST'},
            '/apps/<uuid:app_id>/conversations': {'POST'},
            '/apps/<uuid:app_id>/conversations/delete-debug-conversation': {'POST'},
            '/apps/<uuid:app_id>/conversations/messages': {'GET'},
            '/apps/<uuid:app_id>/conversations/tasks/<uuid:task_id>/stop': {'POST'},
            '/apps/<uuid:app_id>/copy': {'POST'},
            '/apps/<uuid:app_id>/delete': {'POST'},
            '/apps/<uuid:app_id>/draft-app-config': {'GET', 'POST'},
            '/apps/<uuid:app_id>/fallback-history': {'POST'},
            '/apps/<uuid:app_id>/publish': {'POST'},
            '/apps/<uuid:app_id>/publish-histories': {'GET'},
            '/apps/<uuid:app_id>/published-config': {'GET'},
            '/apps/<uuid:app_id>/published-config/regenerate-web-app-token': {'POST'},
            '/apps/<uuid:app_id>/regenerate-icon': {'POST'},
            '/apps/<uuid:app_id>/share-to-square': {'POST'},
            '/apps/<uuid:app_id>/summary': {'GET', 'POST'},
            '/apps/<uuid:app_id>/unshare-from-square': {'POST'},
            '/apps/generate-icon-preview': {'POST'},
            '/assistant-agent/chat': {'POST'},
            '/assistant-agent/chat/<uuid:task_id>/stop': {'POST'},
            '/assistant-agent/conversations': {'GET'},
            '/assistant-agent/delete-conversation': {'POST'},
            '/assistant-agent/introduction': {'POST'},
            '/assistant-agent/messages': {'GET'},
            '/audio/audio-to-text': {'POST'},
            '/audio/message-to-audio': {'POST'},
            '/audio/text-to-audio': {'POST'},
            '/auth/logout': {'POST'},
            '/auth/password-login': {'POST'},
            '/auth/reset-password': {'POST'},
            '/auth/send-reset-code': {'POST'},
            '/builtin-tools': {'GET'},
            '/builtin-tools/<string:provider_name>/icon': {'GET'},
            '/builtin-tools/<string:provider_name>/tools/<string:tool_name>': {'GET'},
            '/builtin-tools/categories': {'GET'},
            '/conversations/<uuid:conversation_id>/delete': {'POST'},
            '/conversations/<uuid:conversation_id>/is-pinned': {'POST'},
            '/conversations/<uuid:conversation_id>/messages': {'GET'},
            '/conversations/<uuid:conversation_id>/messages/<uuid:message_id>': {'POST'},
            '/conversations/<uuid:conversation_id>/messages/<uuid:message_id>/delete': {'POST'},
            '/conversations/<uuid:conversation_id>/name': {'GET', 'POST'},
            '/conversations/recent': {'GET'},
            '/datasets': {'GET', 'POST'},
            '/datasets/<uuid:dataset_id>': {'GET', 'POST'},
            '/datasets/<uuid:dataset_id>/delete': {'POST'},
            '/datasets/<uuid:dataset_id>/documents': {'GET', 'POST'},
            '/datasets/<uuid:dataset_id>/documents/<uuid:document_id>': {'GET'},
            '/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/delete': {'POST'},
            '/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/enabled': {'POST'},
            '/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/name': {'POST'},
            '/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/segments': {'GET', 'POST'},
            '/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/segments/<uuid:segment_id>': {'GET', 'POST'},
            '/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/segments/<uuid:segment_id>/delete': {'POST'},
            '/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/segments/<uuid:segment_id>/enabled': {'POST'},
            '/datasets/<uuid:dataset_id>/documents/batch/<string:batch>': {'GET'},
            '/datasets/<uuid:dataset_id>/hit': {'POST'},
            '/datasets/<uuid:dataset_id>/queries': {'GET'},
            '/datasets/<uuid:dataset_id>/regenerate-icon': {'POST'},
            '/datasets/generate-icon-preview': {'POST'},
            '/health': {'GET'},
            '/language-models': {'GET'},
            '/language-models/<string:provider_name>/<string:model_name>': {'GET'},
            '/language-models/<string:provider_name>/icon': {'GET'},
            '/oauth/<string:provider_name>': {'GET'},
            '/oauth/authorize/<string:provider_name>': {'POST'},
            '/openapi/api-keys': {'GET', 'POST'},
            '/openapi/api-keys/<uuid:api_key_id>': {'POST'},
            '/openapi/api-keys/<uuid:api_key_id>/delete': {'POST'},
            '/openapi/api-keys/<uuid:api_key_id>/is-active': {'POST'},
            '/openapi/chat': {'POST'},
            '/ping': {'GET'},
            '/platform/<uuid:app_id>/wechat-config': {'GET', 'POST'},
            '/public/apps': {'GET'},
            '/public/apps/<string:app_id>': {'GET'},
            '/public/apps/<string:app_id>/analysis': {'GET'},
            '/public/apps/<string:app_id>/fork': {'POST'},
            '/public/apps/<uuid:app_id>/favorite': {'POST'},
            '/public/apps/<uuid:app_id>/like': {'POST'},
            '/public/apps/categories': {'GET'},
            '/public/apps/my-favorites': {'GET'},
            '/public/workflows': {'GET'},
            '/public/workflows/<uuid:workflow_id>': {'GET'},
            '/public/workflows/<uuid:workflow_id>/draft-graph': {'GET'},
            '/public/workflows/<uuid:workflow_id>/favorite': {'POST'},
            '/public/workflows/<uuid:workflow_id>/fork': {'POST'},
            '/public/workflows/<uuid:workflow_id>/like': {'POST'},
            '/upload-files/file': {'POST'},
            '/upload-files/image': {'POST'},
            '/web-apps/<string:token>': {'GET'},
            '/web-apps/<string:token>/chat': {'POST'},
            '/web-apps/<string:token>/chat/<uuid:task_id>/stop': {'POST'},
            '/web-apps/<string:token>/conversations': {'GET'},
            '/wechat/<uuid:app_id>': {'GET', 'POST'},
            '/workflows': {'GET', 'POST'},
            '/workflows/<uuid:workflow_id>': {'GET', 'POST'},
            '/workflows/<uuid:workflow_id>/cancel-publish': {'POST'},
            '/workflows/<uuid:workflow_id>/debug': {'POST'},
            '/workflows/<uuid:workflow_id>/delete': {'POST'},
            '/workflows/<uuid:workflow_id>/draft-graph': {'GET', 'POST'},
            '/workflows/<uuid:workflow_id>/publish': {'POST'},
            '/workflows/<uuid:workflow_id>/regenerate-icon': {'POST'},
            '/workflows/<uuid:workflow_id>/share': {'POST'},
            '/workflows/<uuid:workflow_id>/share-to-square': {'POST'},
            '/workflows/<uuid:workflow_id>/unshare-from-square': {'POST'},
            '/workflows/generate-icon-preview': {'POST'},
        }

        assert dict(route_methods) == expected

    def test_should_keep_blueprint_and_method_constraints(self, app):
        assert set(app.blueprints.keys()) == {"llmops", "openapi"}

        rules = [rule for rule in app.url_map.iter_rules() if rule.endpoint != "static"]
        by_blueprint = defaultdict(int)
        for rule in rules:
            blueprint_name = rule.endpoint.split(".", 1)[0]
            by_blueprint[blueprint_name] += 1
            assert _methods(rule).issubset({"GET", "POST"})
            assert len(_methods(rule)) >= 1

        assert by_blueprint["openapi"] == 1
        assert by_blueprint["llmops"] == len(rules) - 1
        # 当前系统的接口总量是一个重要契约，避免漏挂导致线上能力消失。
        assert len(rules) == 140
