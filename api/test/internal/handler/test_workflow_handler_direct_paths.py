from types import SimpleNamespace

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
