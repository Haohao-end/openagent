from types import SimpleNamespace

import pytest
from flask import Flask

from internal.handler.workflow_handler import WorkflowHandler
from pkg.response import HttpCode


@pytest.mark.parametrize("payload", [None, {}, [], {"is_public": "false"}])
def test_share_workflow_should_reject_missing_or_non_boolean_visibility(monkeypatch, payload):
    service = SimpleNamespace(
        share_workflow_to_public=lambda *_args: pytest.fail("invalid payload changed visibility")
    )
    handler = WorkflowHandler(workflow_service=service)
    monkeypatch.setattr("internal.handler.workflow_handler.current_user", SimpleNamespace(id="user"))
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/workflows/workflow-id/share", method="POST", json=payload
    ):
        response, status_code = handler.share_workflow_to_public.__wrapped__(
            handler, "workflow-id"
        )

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.VALIDATE_ERROR
