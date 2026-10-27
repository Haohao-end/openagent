from types import SimpleNamespace

import pytest
from flask import Flask

from internal.handler.skill_handler import SkillHandler
from pkg.response import HttpCode


@pytest.mark.parametrize("payload", ["invalid", 1])
def test_rollback_skill_package_should_validate_non_object_json(monkeypatch, payload):
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
