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

    def test_get_public_apps_with_page_unauthenticated(self, app):
        from pkg.paginator import Paginator

        calls = []
        paginator = Paginator(db=None)
        service = SimpleNamespace(
            get_public_apps_with_page=lambda req, account: (calls.append(account), ([], paginator))[1]
        )
        handler = PublicAppHandler(public_app_service=service, public_agent_a2a_service=None)

        with app.test_request_context("/public/apps?current_page=1&page_size=20"):
            resp, status_code = handler.get_public_apps_with_page()

        assert status_code == 200
        assert calls == [None]

    def test_get_public_app_detail_unauthenticated(self, app):
        calls = []
        service = SimpleNamespace(
            get_public_app_detail=lambda app_id, account: (calls.append((app_id, account)), {"id": app_id})[1]
        )
        handler = PublicAppHandler(public_app_service=service, public_agent_a2a_service=None)

        with app.test_request_context("/public/apps/test-app"):
            resp, status_code = handler.get_public_app_detail("test-app")

        assert status_code == 200
        assert calls == [("test-app", None)]
