import asyncio
import importlib
import json

import pytest

from internal.core.tools.builtin_tools.providers.dalle.dalle3 import Dalle3ArgsSchema, dalle3
from internal.core.tools.builtin_tools.providers.duckduckgo.duckduckgo_search import DDGInput, duckduckgo_search
from internal.core.tools.builtin_tools.providers.gaode.gaode_weather import GaodeWeatherTool, gaode_weather
from internal.core.tools.builtin_tools.providers.google.google_serper import (
    GoogleSerperArgsSchema,
    google_serper,
)
from internal.core.tools.builtin_tools.providers.time.current_time import CurrentTimeTool, current_time
from internal.core.tools.builtin_tools.providers.wikipedia.wikipedia_search import wikipedia_search


def test_gaode_weather_tool_should_cover_success_failure_and_exception(monkeypatch):
    gaode_module = importlib.import_module("internal.core.tools.builtin_tools.providers.gaode.gaode_weather")

    class _FakeResponse:
        def __init__(self, payload, should_raise=False):
            self._payload = payload
            self._should_raise = should_raise

        def raise_for_status(self):
            if self._should_raise:
                raise RuntimeError("boom")

        def json(self):
            return self._payload

    class _FakeSession:
        def __init__(self, responses):
            self.responses = responses
            self.calls = []

        def request(self, **kwargs):
            self.calls.append(kwargs)
            return self.responses.pop(0)

    tool = GaodeWeatherTool()

    monkeypatch.delenv("GAODE_API_KEY", raising=False)
    assert tool._run(city="广州") == "高德开放平台API未配置"

    monkeypatch.setenv("GAODE_API_KEY", "token")
    success_session = _FakeSession(
        [
            _FakeResponse({"info": "OK", "districts": [{"adcode": "440100"}]}),
            _FakeResponse({"info": "OK", "forecasts": [{"date": "2026-02-26"}]}),
        ]
    )
    monkeypatch.setattr(gaode_module.requests, "session", lambda: success_session)
    success = tool._run(city="广州")
    assert json.loads(success)["info"] == "OK"
    assert len(success_session.calls) == 2

    failure_session = _FakeSession([_FakeResponse({"info": "FAIL"})])
    monkeypatch.setattr(gaode_module.requests, "session", lambda: failure_session)
    assert tool._run(city="深圳") == "获取深圳天气预报信息失败"

    # 覆盖 city 成功但 weather 接口返回非 OK 的分支。
    weather_fail_session = _FakeSession(
        [
            _FakeResponse({"info": "OK", "districts": [{"adcode": "440300"}]}),
            _FakeResponse({"info": "FAIL"}),
        ]
    )
    monkeypatch.setattr(gaode_module.requests, "session", lambda: weather_fail_session)
    assert tool._run(city="深圳") == "获取深圳天气预报信息失败"

    exception_session = _FakeSession([_FakeResponse({}, should_raise=True)])
    monkeypatch.setattr(gaode_module.requests, "session", lambda: exception_session)
    assert tool._run(city="北京") == "获取北京天气预报信息失败"


def test_current_time_tool_and_factory_should_work():
    tool = CurrentTimeTool()
    result = tool._run()
    # 固定断言到前 19 位，避免时区字符串在不同环境下表现不一致。
    assert len(result[:19]) == 19
    assert result[4] == "-" and result[7] == "-"
    assert asyncio.run(tool._arun())[:19] == result[:19]
    assert isinstance(current_time(), CurrentTimeTool)


def test_builtin_tool_factories_should_construct_wrapped_tools(monkeypatch):
    google_module = importlib.import_module("internal.core.tools.builtin_tools.providers.google.google_serper")
    ddg_module = importlib.import_module("internal.core.tools.builtin_tools.providers.duckduckgo.duckduckgo_search")
    wiki_module = importlib.import_module("internal.core.tools.builtin_tools.providers.wikipedia.wikipedia_search")
    dalle_module = importlib.import_module("internal.core.tools.builtin_tools.providers.dalle.dalle3")
    captured = {}

    class _FakeGoogleWrapper:
        pass

    class _FakeGoogleRun:
        def __init__(self, **kwargs):
            captured["google"] = kwargs

    class _FakeDDGRun:
        def __init__(self, **kwargs):
            captured["ddg"] = kwargs

    class _FakeWikipediaWrapper:
        pass

    class _FakeWikipediaRun:
        def __init__(self, **kwargs):
            captured["wiki"] = kwargs

    class _FakeDalleWrapper:
        def __init__(self, **kwargs):
            captured["dalle_wrapper"] = kwargs

    class _FakeDalleTool:
        def __init__(self, **kwargs):
            captured["dalle_tool"] = kwargs

    monkeypatch.setattr(google_module, "GoogleSerperAPIWrapper", _FakeGoogleWrapper)
    monkeypatch.setattr(google_module, "GoogleSerperRun", _FakeGoogleRun)
    monkeypatch.setattr(ddg_module, "DuckDuckGoSearchRun", _FakeDDGRun)
    monkeypatch.setattr(wiki_module, "WikipediaAPIWrapper", _FakeWikipediaWrapper)
    monkeypatch.setattr(wiki_module, "WikipediaQueryRun", _FakeWikipediaRun)
    monkeypatch.setattr(dalle_module, "DallEAPIWrapper", _FakeDalleWrapper)
    monkeypatch.setattr(dalle_module, "OpenAIDALLEImageGenerationTool", _FakeDalleTool)

    google_serper()
    duckduckgo_search()
    wikipedia_search()
    dalle3(size="1024x1024")

    assert captured["google"]["args_schema"] is GoogleSerperArgsSchema
    assert captured["ddg"]["args_schema"] is DDGInput
    assert isinstance(captured["wiki"]["api_wrapper"], _FakeWikipediaWrapper)
    assert captured["dalle_wrapper"]["model"] == "dall-e-3"
    assert captured["dalle_wrapper"]["size"] == "1024x1024"
    assert captured["dalle_tool"]["args_schema"] is Dalle3ArgsSchema


def test_gaode_weather_factory_should_return_tool_instance():
    assert isinstance(gaode_weather(), GaodeWeatherTool)
