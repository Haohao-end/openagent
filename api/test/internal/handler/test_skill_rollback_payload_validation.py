from types import SimpleNamespace

import pytest
from flask import Flask

from internal.handler.skill_handler import SkillHandler
from pkg.response import HttpCode


@pytest.mark.parametrize("payload", ["invalid", 1, {"version": True}, {"version": False}])
def test_rollback_skill_package_should_validate_invalid_json_payloads(monkeypatch, payload):
    handler = SkillHandler(
        skill_service=SimpleNamespace(
            rollback_skill_package=lambda *_args: pytest.fail("invalid payload reached service")
        )
    )
    monkeypatch.setattr("internal.handler.skill_handler.login_required", lambda fn: fn)
    test_app = Flask(__name__)
    test_app.config["WTF_CSRF_ENABLED"] = False

    with test_app.test_request_context(
        "/skills/packages/skill-id/rollback", method="POST", json=payload
    ):
        response, status_code = handler.rollback_skill_package.__wrapped__(
            handler, "skill-id"
        )

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.VALIDATE_ERROR


def test_rollback_skill_package_should_accept_integer_version(monkeypatch):
    calls = []
    handler = SkillHandler(
        skill_service=SimpleNamespace(rollback_skill_package=lambda *args: calls.append(args))
    )
    monkeypatch.setattr("internal.handler.skill_handler.login_required", lambda fn: fn)
    test_app = Flask(__name__)
    test_app.config["WTF_CSRF_ENABLED"] = False

    with test_app.test_request_context(
        "/skills/packages/skill-id/rollback", method="POST", json={"version": 1}
    ):
        _, status_code = handler.rollback_skill_package.__wrapped__(handler, "skill-id")

    assert status_code == 200
    assert calls == [("skill-id", 1)]
