from types import SimpleNamespace
from uuid import uuid4

from internal.entity.app_entity import AppStatus
from internal.entity.platform_entity import WechatConfigStatus
from internal.service.platform_service import PlatformService


def _build_req(app_id="wx-app", app_secret="wx-secret", token="wx-token"):
    return SimpleNamespace(
        wechat_app_id=SimpleNamespace(data=app_id),
        wechat_app_secret=SimpleNamespace(data=app_secret),
        wechat_token=SimpleNamespace(data=token),
    )


class TestPlatformService:
    def test_get_wechat_config_should_return_config_from_app(self):
        wechat_config = SimpleNamespace(status=WechatConfigStatus.UNCONFIGURED)
        app = SimpleNamespace(wechat_config=wechat_config)
        app_service = SimpleNamespace(get_app=lambda _app_id, _account: app)
        service = PlatformService(db=SimpleNamespace(), app_service=app_service)

        result = service.get_wechat_config(uuid4(), SimpleNamespace())

        assert result is wechat_config

    def test_update_wechat_config_should_mark_configured_when_all_fields_present(self, monkeypatch):
        wechat_config = SimpleNamespace(
            wechat_app_id="",
            wechat_app_secret="",
            wechat_token="",
            status=WechatConfigStatus.UNCONFIGURED,
        )
        app = SimpleNamespace(status=AppStatus.PUBLISHED, wechat_config=wechat_config)
        app_service = SimpleNamespace(get_app=lambda _app_id, _account: app)
        service = PlatformService(db=SimpleNamespace(), app_service=app_service)

        updates = {}
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.update({"target": target, "kwargs": kwargs}) or target,
        )

        result = service.update_wechat_config(uuid4(), _build_req(), SimpleNamespace())

        assert result is wechat_config
        assert updates["target"] is wechat_config
        assert updates["kwargs"]["status"] == WechatConfigStatus.CONFIGURED

    def test_update_wechat_config_should_keep_unconfigured_when_missing_field(self, monkeypatch):
        wechat_config = SimpleNamespace(
            wechat_app_id="",
            wechat_app_secret="",
            wechat_token="",
            status=WechatConfigStatus.UNCONFIGURED,
        )
        app = SimpleNamespace(status=AppStatus.PUBLISHED, wechat_config=wechat_config)
        app_service = SimpleNamespace(get_app=lambda _app_id, _account: app)
        service = PlatformService(db=SimpleNamespace(), app_service=app_service)

        updates = {}
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.update({"target": target, "kwargs": kwargs}) or target,
        )

        service.update_wechat_config(
            uuid4(),
            _build_req(app_id="wx-app", app_secret="wx-secret", token=""),
            SimpleNamespace(),
        )

        assert updates["kwargs"]["status"] == WechatConfigStatus.UNCONFIGURED

    def test_update_wechat_config_should_force_unconfigured_when_app_draft(self, monkeypatch):
        wechat_config = SimpleNamespace(
            wechat_app_id="",
            wechat_app_secret="",
            wechat_token="",
            status=WechatConfigStatus.UNCONFIGURED,
        )
        app = SimpleNamespace(status=AppStatus.DRAFT, wechat_config=wechat_config)
        app_service = SimpleNamespace(get_app=lambda _app_id, _account: app)
        service = PlatformService(db=SimpleNamespace(), app_service=app_service)

        updates = {}
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.update({"target": target, "kwargs": kwargs}) or target,
        )

        service.update_wechat_config(uuid4(), _build_req(), SimpleNamespace())

        assert updates["kwargs"]["status"] == WechatConfigStatus.UNCONFIGURED
