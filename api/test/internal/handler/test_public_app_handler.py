from types import SimpleNamespace

from internal.handler.public_app_handler import PublicAppHandler


class TestPublicAppHandler:
    def test_send_public_app_a2a_message_should_return_sse_stream(self, app):
        service = SimpleNamespace(
            stream_message=lambda _app_id, _payload: iter(
                [
                    'event: message\ndata: {"hello":"world"}\n\n',
                ]
            )
        )
        handler = PublicAppHandler(
            public_app_service=SimpleNamespace(),
            analysis_service=SimpleNamespace(),
            public_agent_a2a_service=service,
        )

        with app.test_request_context(
            "/public/apps/demo-app/a2a/messages",
            method="POST",
            json={"message": {"parts": [{"type": "text", "text": "hello"}]}},
        ):
            resp = handler.send_public_app_a2a_message("demo-app")

        assert resp.status_code == 200
        assert resp.mimetype == "text/event-stream"
        assert 'event: message' in resp.get_data(as_text=True)
        assert '{"hello":"world"}' in resp.get_data(as_text=True)
