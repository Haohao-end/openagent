from types import SimpleNamespace

import pytest
from flask import Flask

from internal.handler.workflow_handler import WorkflowHandler
from pkg.response import HttpCode


@pytest.mark.parametrize("payload", [[], "invalid", 1])
def test_debug_workflow_should_reject_non_object_inputs(monkeypatch, payload):
    service = SimpleNamespace(
        debug_workflow=lambda *_args: pytest.fail("invalid inputs reached workflow service")
    )
    handler = WorkflowHandler(workflow_service=service)
    monkeypatch.setattr("internal.handler.workflow_handler.current_user", SimpleNamespace(id="user"))
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/workflows/workflow-id/debug", method="POST", json=payload
    ):
        response, status_code = handler.debug_workflow.__wrapped__(handler, "workflow-id")

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.VALIDATE_ERROR
