from types import SimpleNamespace

import pytest
from flask import Flask

from internal.handler.workflow_handler import WorkflowHandler
from pkg.response import HttpCode


@pytest.mark.parametrize("payload", [[], "invalid", 1])
def test_update_draft_graph_should_reject_non_object_json(monkeypatch, payload):
    service = SimpleNamespace(
        update_draft_graph=lambda *_args: pytest.fail("invalid graph reached service")
    )
    handler = WorkflowHandler(workflow_service=service)
    monkeypatch.setattr("internal.handler.workflow_handler.current_user", SimpleNamespace(id="user"))
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/workflows/workflow-id/draft-graph", method="PUT", json=payload
    ):
        response, status_code = handler.update_draft_graph.__wrapped__(
            handler, "workflow-id"
        )

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.VALIDATE_ERROR


def test_update_draft_graph_should_keep_empty_body_default(monkeypatch):
    captured = {}
    service = SimpleNamespace(
        update_draft_graph=lambda *_args: captured.update(graph=_args[1])
    )
    handler = WorkflowHandler(workflow_service=service)
    monkeypatch.setattr("internal.handler.workflow_handler.current_user", SimpleNamespace(id="user"))
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/workflows/workflow-id/draft-graph", method="PUT"
    ):
        response, status_code = handler.update_draft_graph.__wrapped__(
            handler, "workflow-id"
        )

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.SUCCESS
    assert captured["graph"] == {"nodes": [], "edges": []}
