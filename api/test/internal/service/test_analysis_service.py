import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from internal.service.analysis_service import AnalysisService


def _message(created_at: datetime, conversation_id=None, created_by=None, latency=1.0, tokens=10, price=0.2):
    return SimpleNamespace(
        conversation_id=conversation_id or uuid4(),
        created_by=created_by or uuid4(),
        latency=latency,
        total_token_count=tokens,
        total_price=price,
        created_at=created_at,
    )


def _build_service(app=None):
    return AnalysisService(
        db=SimpleNamespace(session=SimpleNamespace()),
        app_service=SimpleNamespace(get_app=lambda *_args, **_kwargs: app or SimpleNamespace(id=uuid4())),
    )


class TestAnalysisService:
    def test_get_app_analysis_should_calculate_realtime_data(self, monkeypatch):
        """测试实时计算统计数据(不使用缓存)"""
        app = SimpleNamespace(id=uuid4())
        now = datetime.now()
        midnight = datetime.combine(now, datetime.min.time())

        recent_messages = [
            _message(created_at=midnight - timedelta(days=1), latency=2.0, tokens=100, price=0.5),
            _message(created_at=midnight - timedelta(days=2), latency=1.0, tokens=40, price=0.2),
        ]
        previous_messages = [
            _message(created_at=midnight - timedelta(days=8), latency=1.0, tokens=20, price=0.1),
        ]
        message_sets = [recent_messages, previous_messages]

        service = _build_service(app=app)

        monkeypatch.setattr(
            service,
            "get_messages_by_time_range",
            lambda *_args, **_kwargs: message_sets.pop(0),
        )

        result = service.get_app_analysis(app.id, SimpleNamespace(id=uuid4()))

        assert result["total_messages"]["data"] == 2
        assert result["active_accounts"]["data"] >= 1
        assert len(result["total_messages_trend"]["x_axis"]) == 7
        assert len(result["total_messages_trend"]["y_axis"]) == 7

    def test_get_app_analysis_should_handle_empty_messages(self, monkeypatch):
        """测试空消息列表的处理"""
        app = SimpleNamespace(id=uuid4())
        message_sets = [[], []]
        service = _build_service(app=app)
        monkeypatch.setattr(
            service,
            "get_messages_by_time_range",
            lambda *_args, **_kwargs: message_sets.pop(0),
        )

        result = service.get_app_analysis(app.id, SimpleNamespace(id=uuid4()))

        assert result["total_messages"]["data"] == 0

    def test_calculate_overview_indicators_should_handle_zero_division_safely(self):
        indicators = AnalysisService.calculate_overview_indicators_by_messages([])

        assert indicators["total_messages"] == 0
        assert indicators["active_accounts"] == 0
        assert indicators["avg_of_conversation_messages"] == 0.0
        assert indicators["token_output_rate"] == 0.0
        assert indicators["cost_consumption"] == 0.0

    def test_calculate_pop_should_handle_previous_zero(self):
        current = {
            "total_messages": 10,
            "active_accounts": 3,
            "avg_of_conversation_messages": 2.5,
            "token_output_rate": 30.0,
            "cost_consumption": 6.0,
        }
        previous = {
            "total_messages": 5,
            "active_accounts": 0,
            "avg_of_conversation_messages": 2.0,
            "token_output_rate": 0.0,
            "cost_consumption": 3.0,
        }

        pop = AnalysisService.calculate_pop_by_overview_indicators(current, previous)

        assert pop["total_messages"] == pytest.approx(1.0)
        assert pop["active_accounts"] == 0.0
        assert pop["avg_of_conversation_messages"] == pytest.approx(0.25)
        assert pop["token_output_rate"] == 0.0
        assert pop["cost_consumption"] == pytest.approx(1.0)

    def test_get_messages_by_time_range_should_use_query_pipeline(self):
        messages = [SimpleNamespace(id=uuid4())]

        class _Query:
            def __init__(self):
                self.with_entities_called = False
                self.filter_called = False

            def with_entities(self, *_args, **_kwargs):
                self.with_entities_called = True
                return self

            def filter(self, *_args, **_kwargs):
                self.filter_called = True
                return self

            def all(self):
                return messages

        query = _Query()
        service = AnalysisService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: query)),
            app_service=SimpleNamespace(),
        )
        app = SimpleNamespace(id=uuid4())
        start_at = datetime(2024, 1, 1, 0, 0, 0)
        end_at = datetime(2024, 1, 2, 0, 0, 0)

        result = service.get_messages_by_time_range(app, start_at, end_at)

        assert query.with_entities_called is True
        assert query.filter_called is True
        assert result == messages

    def test_calculate_trend_by_messages_should_generate_fixed_length_series(self):
        end_at = datetime(2024, 1, 8, 18, 30, 0)
        messages = [
            _message(created_at=datetime(2024, 1, 2, 10, 0, 0), price=0.2),
            _message(created_at=datetime(2024, 1, 2, 11, 0, 0), price=0.4),
            _message(created_at=datetime(2024, 1, 5, 8, 0, 0), price=0.6),
        ]

        trend = AnalysisService.calculate_trend_by_messages(end_at=end_at, days_ago=7, messages=messages)

        assert len(trend["total_messages_trend"]["x_axis"]) == 7
        assert len(trend["total_messages_trend"]["y_axis"]) == 7
        assert len(trend["active_accounts_trend"]["y_axis"]) == 7
        assert len(trend["avg_of_conversation_messages_trend"]["y_axis"]) == 7
        assert len(trend["cost_consumption_trend"]["y_axis"]) == 7
