def _methods(rule):
    return frozenset(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})


class TestRouterContract:
    """路由契约测试，防止接口意外删改。"""

    def test_should_register_core_routes(self, app):
        rules = {(rule.rule, _methods(rule)) for rule in app.url_map.iter_rules() if rule.endpoint != "static"}

        expected = {
            ("/ping", frozenset({"GET"})),
            ("/apps", frozenset({"GET"})),
            ("/apps", frozenset({"POST"})),
            ("/apps/<uuid:app_id>/conversations", frozenset({"POST"})),
            ("/apps/<uuid:app_id>/prompt-compare/chat", frozenset({"POST"})),
            ("/api-tools/validate-openapi-schema", frozenset({"POST"})),
            ("/datasets/<uuid:dataset_id>/hit", frozenset({"POST"})),
            ("/openapi/chat", frozenset({"POST"})),
            ("/assistant-agent/chat", frozenset({"POST"})),
            ("/web-apps/<string:token>/chat", frozenset({"POST"})),
            ("/conversations/<uuid:conversation_id>/name", frozenset({"GET"})),
            ("/conversations/<uuid:conversation_id>/name", frozenset({"POST"})),
            ("/audio/audio-to-text", frozenset({"POST"})),
            ("/platform/<uuid:app_id>/wechat-config", frozenset({"GET"})),
            ("/platform/<uuid:app_id>/wechat-config", frozenset({"POST"})),
            ("/wechat/<uuid:app_id>", frozenset({"GET", "POST"})),
        }

        for item in expected:
            assert item in rules

    def test_should_keep_route_surface_size(self, app):
        rules = [rule for rule in app.url_map.iter_rules() if rule.endpoint != "static"]
        # 当前系统接口较多，设定下限避免批量路由被误删时无人感知
        assert len(rules) >= 80
