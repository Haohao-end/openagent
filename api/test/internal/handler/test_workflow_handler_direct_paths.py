from types import SimpleNamespace
from uuid import uuid4

from pkg.response import HttpCode
from internal.handler.workflow_handler import WorkflowHandler


class TestWorkflowHandlerDirectPaths:
    def test_generate_icon_preview_should_delegate_and_return_icon(self, app):
        service = SimpleNamespace(
            generate_icon_preview=lambda name, description: f"https://a.com/{name}-{description}.png"
        )
        handler = WorkflowHandler(workflow_service=service)

        with app.test_request_context(
            "/workflows/generate-icon-preview",
            method="POST",
            json={"name": "wf", "description": "demo"},
        ):
            resp, status_code = handler.generate_icon_preview()

        assert status_code == 200
        payload = resp.get_json()
        assert payload["code"] == HttpCode.SUCCESS
        assert payload["data"]["icon"] == "https://a.com/wf-demo.png"

    def test_get_workflow_result_trace_should_delegate_and_return_trace(self, app):
        workflow_id = uuid4()
        result_id = uuid4()
        expected = {
            "id": str(result_id),
            "workflow_id": str(workflow_id),
            "status": "succeeded",
            "latency": 0.5,
            "steps": [],
        }
        service = SimpleNamespace(
            get_workflow_result_trace=lambda wid, rid, _user: expected
        )
        handler = WorkflowHandler(workflow_service=service)

        with app.test_request_context(
            f"/workflows/{workflow_id}/results/{result_id}/trace",
            method="GET",
        ):
            resp, status_code = handler.get_workflow_result_trace(workflow_id, result_id)

        assert status_code == 200
        payload = resp.get_json()
        assert payload["code"] == HttpCode.SUCCESS
        assert payload["data"] == expected
