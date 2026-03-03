import runpy
import sys


def test_app_module_should_call_run_when_executed_as_main(monkeypatch):
    import internal.server as server_module

    run_calls = []

    class _FakeHttp:
        def __init__(self, *_args, **_kwargs):
            self.extensions = {"celery": "celery-app"}

        def run(self, **kwargs):
            run_calls.append(kwargs)

    monkeypatch.setattr(server_module, "Http", _FakeHttp)
    monkeypatch.delitem(sys.modules, "app.http.app", raising=False)

    module_globals = runpy.run_module("app.http.app", run_name="__main__")

    assert run_calls == [{"debug": True, "port": 5001}]
    assert module_globals["celery"] == "celery-app"
