import pytest
from types import SimpleNamespace
from internal.handler.app_handler import AppHandler
from pkg.response import HttpCode


class TestAppHandler:
    """app控制器的测试类"""

    @pytest.fixture
    def http_client(self, app):
        """使用独立客户端，避免触发全局 client->db 自动事务夹具。"""
        with app.test_client() as client:
            yield client

    @pytest.mark.parametrize(
        "app_id, query",
        [
            ("e0d13c78-870b-46df-b2f5-693ae9d5d727", None),
            ("e0d13c78-870b-46df-b2f5-693ae9d5d727", ""),
        ]
    )
    def test_completion(self, app_id, query, http_client):
        resp = http_client.post(f"/apps/{app_id}/conversations", json={"query": query})
        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.VALIDATE_ERROR

    def test_regenerate_icon_success(self, http_client, login_account, monkeypatch):
        """测试重新生成图标成功"""
        from uuid import uuid4
        from unittest.mock import Mock
        from internal.service import AppService

        app_id = uuid4()
        new_icon_url = "https://cos.com/new-icon.png"

        # Mock app service regenerate_icon method
        mock_regenerate_icon = Mock(return_value=new_icon_url)
        monkeypatch.setattr(AppService, "regenerate_icon", mock_regenerate_icon)

        resp = http_client.post(f"/apps/{app_id}/regenerate-icon")

        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        assert resp.json.get("data").get("icon") == new_icon_url

    def test_regenerate_icon_not_found(self, http_client, login_account, monkeypatch):
        """测试重新生成图标时应用不存在"""
        from uuid import uuid4
        from unittest.mock import Mock
        from internal.service import AppService
        from internal.exception import NotFoundException

        app_id = uuid4()

        # Mock app service to raise NotFoundException
        mock_regenerate_icon = Mock(side_effect=NotFoundException("应用不存在"))
        monkeypatch.setattr(AppService, "regenerate_icon", mock_regenerate_icon)

        resp = http_client.post(f"/apps/{app_id}/regenerate-icon")

        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.NOT_FOUND

    @staticmethod
    def _new_app_handler(*, db_execute=None, redis_ping=None):
        db_execute = db_execute or (lambda _sql: None)
        redis_ping = redis_ping or (lambda: None)
        app_service = SimpleNamespace(
            db=SimpleNamespace(session=SimpleNamespace(execute=db_execute)),
            redis_client=SimpleNamespace(ping=redis_ping),
        )
        return AppHandler(
            app_service=app_service,
            retrieval_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
        )

    def test_probe_database_should_return_healthy_when_select_one_success(self):
        handler = self._new_app_handler()

        result = handler._probe_database()

        assert result == {"status": "healthy", "detail": ""}

    def test_probe_database_should_return_unhealthy_when_query_failed(self):
        handler = self._new_app_handler(
            db_execute=lambda _sql: (_ for _ in ()).throw(RuntimeError("db-down"))
        )

        result = handler._probe_database()

        assert result["status"] == "unhealthy"
        assert "db-down" in result["detail"]

    def test_probe_redis_should_return_healthy_when_ping_success(self):
        handler = self._new_app_handler()

        result = handler._probe_redis()

        assert result == {"status": "healthy", "detail": ""}

    def test_probe_redis_should_return_unhealthy_when_ping_failed(self):
        handler = self._new_app_handler(
            redis_ping=lambda: (_ for _ in ()).throw(RuntimeError("redis-down"))
        )

        result = handler._probe_redis()

        assert result["status"] == "unhealthy"
        assert "redis-down" in result["detail"]

    def test_probe_weaviate_should_return_skipped_when_extension_missing(self, app):
        with app.app_context():
            original = app.extensions.get("weaviate")
            app.extensions.pop("weaviate", None)
            try:
                result = AppHandler._probe_weaviate()
            finally:
                if original is not None:
                    app.extensions["weaviate"] = original

        assert result["status"] == "skipped"

    def test_probe_weaviate_should_return_skipped_when_client_is_none(self, app):
        with app.app_context():
            original = app.extensions.get("weaviate")
            app.extensions["weaviate"] = SimpleNamespace(client=None)
            try:
                result = AppHandler._probe_weaviate()
            finally:
                if original is not None:
                    app.extensions["weaviate"] = original
                else:
                    app.extensions.pop("weaviate", None)

        assert result["status"] == "skipped"

    def test_probe_weaviate_should_return_healthy_when_ready(self, app):
        with app.app_context():
            original = app.extensions.get("weaviate")
            app.extensions["weaviate"] = SimpleNamespace(
                client=SimpleNamespace(is_ready=lambda: True)
            )
            try:
                result = AppHandler._probe_weaviate()
            finally:
                if original is not None:
                    app.extensions["weaviate"] = original

        assert result == {"status": "healthy", "detail": ""}

    def test_probe_weaviate_should_return_unhealthy_when_not_ready(self, app):
        with app.app_context():
            original = app.extensions.get("weaviate")
            app.extensions["weaviate"] = SimpleNamespace(
                client=SimpleNamespace(is_ready=lambda: False)
            )
            try:
                result = AppHandler._probe_weaviate()
            finally:
                if original is not None:
                    app.extensions["weaviate"] = original

        assert result["status"] == "unhealthy"

    def test_probe_weaviate_should_return_unhealthy_when_exception_raised(self, app):
        with app.app_context():
            original = app.extensions.get("weaviate")
            app.extensions["weaviate"] = SimpleNamespace(
                client=SimpleNamespace(
                    is_ready=lambda: (_ for _ in ()).throw(RuntimeError("weaviate-down"))
                )
            )
            try:
                result = AppHandler._probe_weaviate()
            finally:
                if original is not None:
                    app.extensions["weaviate"] = original

        assert result["status"] == "unhealthy"
        assert "weaviate-down" in result["detail"]

    def test_probe_weaviate_should_return_skipped_when_client_is_none(self, app):
        with app.app_context():
            original = app.extensions.get("weaviate")
            app.extensions["weaviate"] = SimpleNamespace(client=None)
            try:
                result = AppHandler._probe_weaviate()
            finally:
                if original is not None:
                    app.extensions["weaviate"] = original

        assert result == {"status": "skipped", "detail": "Weaviate未初始化"}

    def test_probe_weaviate_should_return_unhealthy_when_client_property_raises(self, app):
        """测试访问 weaviate_extension.client 属性时抛异常"""
        class BrokenExtension:
            @property
            def client(self):
                raise RuntimeError("client property broken")

        with app.app_context():
            original = app.extensions.get("weaviate")
            app.extensions["weaviate"] = BrokenExtension()
            try:
                result = AppHandler._probe_weaviate()
            finally:
                if original is not None:
                    app.extensions["weaviate"] = original
                else:
                    app.extensions.pop("weaviate", None)

        assert result["status"] == "unhealthy"
        assert "client property broken" in result["detail"]

    def test_probe_celery_should_return_skipped_when_extension_missing(self, app):
        with app.app_context():
            original = app.extensions.get("celery")
            app.extensions.pop("celery", None)
            try:
                result = AppHandler._probe_celery()
            finally:
                if original is not None:
                    app.extensions["celery"] = original

        assert result["status"] == "skipped"

    def test_probe_celery_should_return_healthy_when_ping_success(self, app):
        with app.app_context():
            original = app.extensions.get("celery")
            app.extensions["celery"] = SimpleNamespace(
                control=SimpleNamespace(
                    inspect=lambda timeout=1: SimpleNamespace(ping=lambda: {"worker@node": {"ok": "pong"}})
                )
            )
            try:
                result = AppHandler._probe_celery()
            finally:
                if original is not None:
                    app.extensions["celery"] = original

        assert result["status"] == "healthy"

    def test_probe_celery_should_return_skipped_when_inspector_is_none(self, app):
        with app.app_context():
            original = app.extensions.get("celery")
            app.extensions["celery"] = SimpleNamespace(
                control=SimpleNamespace(inspect=lambda timeout=1: None)
            )
            try:
                result = AppHandler._probe_celery()
            finally:
                if original is not None:
                    app.extensions["celery"] = original

        assert result["status"] == "skipped"

    def test_probe_celery_should_return_skipped_when_no_active_worker(self, app):
        with app.app_context():
            original = app.extensions.get("celery")
            app.extensions["celery"] = SimpleNamespace(
                control=SimpleNamespace(
                    inspect=lambda timeout=1: SimpleNamespace(ping=lambda: None)
                )
            )
            try:
                result = AppHandler._probe_celery()
            finally:
                if original is not None:
                    app.extensions["celery"] = original

        assert result["status"] == "skipped"

    def test_probe_celery_should_return_unhealthy_when_exception_raised(self, app):
        with app.app_context():
            original = app.extensions.get("celery")
            app.extensions["celery"] = SimpleNamespace(
                control=SimpleNamespace(
                    inspect=lambda timeout=1: (_ for _ in ()).throw(RuntimeError("celery-down"))
                )
            )
            try:
                result = AppHandler._probe_celery()
            finally:
                if original is not None:
                    app.extensions["celery"] = original

        assert result["status"] == "unhealthy"
        assert "celery-down" in result["detail"]

    def test_health_should_return_healthy_when_all_required_and_optional_dependencies_are_healthy(self, app, monkeypatch):
        handler = self._new_app_handler()
        monkeypatch.setattr(handler, "_probe_database", lambda: {"status": "healthy", "detail": ""})
        monkeypatch.setattr(handler, "_probe_redis", lambda: {"status": "healthy", "detail": ""})
        monkeypatch.setattr(handler, "_probe_weaviate", lambda: {"status": "healthy", "detail": ""})
        monkeypatch.setattr(handler, "_probe_celery", lambda: {"status": "healthy", "detail": ""})

        with app.app_context():
            response, status_code = handler.health()

        assert status_code == 200
        payload = response.get_json()
        assert payload["data"]["status"] == "healthy"
        assert payload["data"]["metrics"]["status_code"] == 1
        assert payload["data"]["metrics"]["healthy_components"] == 4
        assert payload["data"]["metrics"]["unhealthy_components"] == 0

    def test_health_should_return_degraded_when_optional_dependency_is_unhealthy(self, app, monkeypatch):
        handler = self._new_app_handler()
        monkeypatch.setattr(handler, "_probe_database", lambda: {"status": "healthy", "detail": ""})
        monkeypatch.setattr(handler, "_probe_redis", lambda: {"status": "unhealthy", "detail": "redis-down"})
        monkeypatch.setattr(handler, "_probe_weaviate", lambda: {"status": "healthy", "detail": ""})
        monkeypatch.setattr(handler, "_probe_celery", lambda: {"status": "skipped", "detail": "no-worker"})

        with app.app_context():
            response, _ = handler.health()

        payload = response.get_json()
        assert payload["data"]["status"] == "degraded"
        assert payload["data"]["metrics"]["status_code"] == 0
        assert payload["data"]["metrics"]["unhealthy_components"] == 1

    def test_health_should_return_unhealthy_when_database_is_unhealthy(self, app, monkeypatch):
        handler = self._new_app_handler()
        monkeypatch.setattr(handler, "_probe_database", lambda: {"status": "unhealthy", "detail": "db-down"})
        monkeypatch.setattr(handler, "_probe_redis", lambda: {"status": "healthy", "detail": ""})
        monkeypatch.setattr(handler, "_probe_weaviate", lambda: {"status": "healthy", "detail": ""})
        monkeypatch.setattr(handler, "_probe_celery", lambda: {"status": "healthy", "detail": ""})

        with app.app_context():
            response, _ = handler.health()

        payload = response.get_json()
        assert payload["data"]["status"] == "unhealthy"
        assert payload["data"]["metrics"]["status_code"] == -1
        assert payload["data"]["metrics"]["unhealthy_components"] == 1

    def test_healthz_should_return_ok_without_probing_dependencies(self, app, monkeypatch):
        handler = self._new_app_handler()
        monkeypatch.setattr(handler, "_probe_database", lambda: pytest.fail("healthz must not probe database"))
        monkeypatch.setattr(handler, "_probe_redis", lambda: pytest.fail("healthz must not probe redis"))
        monkeypatch.setattr(handler, "_probe_weaviate", lambda: pytest.fail("healthz must not probe weaviate"))
        monkeypatch.setattr(handler, "_probe_celery", lambda: pytest.fail("healthz must not probe celery"))

        with app.app_context():
            response, status_code = handler.healthz()

        assert status_code == 200
        payload = response.get_json()
        assert payload["data"] == {
            "status": "ok",
            "service": "llmops-api",
        }

    def test_emit_health_alert_should_not_log_when_status_is_healthy(self, caplog):
        caplog.set_level("WARNING")

        AppHandler._emit_health_alert(
            status="healthy",
            components={"database": {"status": "healthy", "detail": ""}},
            metrics={"status_code": 1},
        )

        assert "健康检查告警" not in caplog.text

    def test_emit_health_alert_should_log_when_status_is_non_healthy(self, caplog):
        caplog.set_level("WARNING")

        AppHandler._emit_health_alert(
            status="degraded",
            components={
                "database": {"status": "healthy", "detail": ""},
                "redis": {"status": "unhealthy", "detail": "redis-down"},
            },
            metrics={"status_code": 0},
        )

        assert "健康检查告警" in caplog.text
        assert "redis" in caplog.text

    def test_probe_database_should_hide_error_detail_in_production(self, app):
        handler = self._new_app_handler(
            db_execute=lambda _sql: (_ for _ in ()).throw(RuntimeError("db-down"))
        )

        previous_testing = app.config.get("TESTING")
        previous_debug = app.debug
        previous_flask_env = app.config.get("FLASK_ENV")
        try:
            app.config["TESTING"] = False
            app.debug = False
            app.config["FLASK_ENV"] = "production"

            with app.app_context():
                result = handler._probe_database()
        finally:
            app.config["TESTING"] = previous_testing
            app.debug = previous_debug
            app.config["FLASK_ENV"] = previous_flask_env

        assert result["status"] == "unhealthy"
        assert result["detail"] == "internal error"

    def test_probe_weaviate_should_hide_error_detail_in_production(self, app):
        previous_testing = app.config.get("TESTING")
        previous_debug = app.debug
        previous_flask_env = app.config.get("FLASK_ENV")

        with app.app_context():
            original = app.extensions.get("weaviate")
            app.extensions["weaviate"] = SimpleNamespace(
                client=SimpleNamespace(
                    is_ready=lambda: (_ for _ in ()).throw(RuntimeError("weaviate-down"))
                )
            )
            try:
                app.config["TESTING"] = False
                app.debug = False
                app.config["FLASK_ENV"] = "production"
                result = AppHandler._probe_weaviate()
            finally:
                app.config["TESTING"] = previous_testing
                app.debug = previous_debug
                app.config["FLASK_ENV"] = previous_flask_env
                if original is not None:
                    app.extensions["weaviate"] = original
                else:
                    app.extensions.pop("weaviate", None)

        assert result["status"] == "unhealthy"
        assert result["detail"] == "internal error"
