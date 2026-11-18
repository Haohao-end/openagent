import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.sql import operators

from internal.core.agent.entities.queue_entity import QueueEvent
from internal.model import MessageAgentThought
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
    dummy_query = SimpleNamespace(
        filter=lambda *_args: SimpleNamespace(scalar=lambda: None, one_or_none=lambda: None)
    )
    return AnalysisService(
        db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: dummy_query)),
        app_service=SimpleNamespace(get_app=lambda *_args, **_kwargs: app or SimpleNamespace(id=uuid4())),
    )


class TestAnalysisService:
    @pytest.mark.parametrize(
        ("previous_rag_latency", "expected_rag_latency_pop"),
        [(2.0, -0.25), (0.0, None), (None, None)],
    )
    def test_get_app_analysis_should_calculate_realtime_data(
        self, monkeypatch, previous_rag_latency, expected_rag_latency_pop,
    ):
        """测试实时计算统计数据(不使用缓存)"""
        app = SimpleNamespace(id=uuid4())
        now = datetime(2024, 1, 8, 18, 30, 0)
        midnight = datetime(2024, 1, 8, 0, 0, 0)

        recent_messages = [
            _message(created_at=midnight - timedelta(days=1), latency=2.0, tokens=100, price=0.5),
            _message(created_at=midnight - timedelta(days=2), latency=1.0, tokens=40, price=0.2),
        ]
        previous_messages = [
            _message(created_at=midnight - timedelta(days=8), latency=1.0, tokens=20, price=0.1),
        ]
        message_sets = [recent_messages, previous_messages]

        service = _build_service(app=app)
        monkeypatch.setattr("internal.service.analysis_service.utc_now_naive", lambda: now)

        monkeypatch.setattr(
            service,
            "get_messages_by_time_range",
            lambda *_args, **_kwargs: message_sets.pop(0),
        )
        retrieval_sets = [1.5, previous_rag_latency]
        monkeypatch.setattr(
            service,
            "get_rag_latency_by_time_range",
            lambda *_args, **_kwargs: retrieval_sets.pop(0),
        )

        result = service.get_app_analysis(app.id, SimpleNamespace(id=uuid4()))

        assert result["total_messages"]["data"] == 2
        assert result["active_accounts"]["data"] >= 1
        assert result["avg_latency"]["data"] == pytest.approx(1.5)
        assert result["rag_retrieval_latency"]["data"] == pytest.approx(1.5)
        actual_pop = result["rag_retrieval_latency"]["pop"]
        if expected_rag_latency_pop is None:
            assert actual_pop is None
        else:
            assert actual_pop == pytest.approx(expected_rag_latency_pop)
        assert len(result["total_messages_trend"]["x_axis"]) == 7
        assert len(result["total_messages_trend"]["y_axis"]) == 7
        assert "rag_hit_rate" in result
        assert "rag_empty_result_rate" in result
        assert "rag_failure_rate" in result
        assert "tool_call_success_rate" in result

    def test_get_app_analysis_should_handle_empty_messages(self, monkeypatch):
        """测试空消息列表的处理"""
        app = SimpleNamespace(id=uuid4())
        message_sets = [[], []]
        service = _build_service(app=app)
        monkeypatch.setattr("internal.service.analysis_service.utc_now_naive", lambda: datetime(2024, 1, 8, 18, 30, 0))
        monkeypatch.setattr(
            service,
            "get_messages_by_time_range",
            lambda *_args, **_kwargs: message_sets.pop(0),
        )
        monkeypatch.setattr(service, "get_rag_latency_by_time_range", lambda *_args: None)

        result = service.get_app_analysis(app.id, SimpleNamespace(id=uuid4()))

        assert result["total_messages"]["data"] == 0
        assert result["avg_latency"]["data"] == 0.0
        assert result["rag_retrieval_latency"] == {"data": None, "pop": None}

    def test_calculate_overview_indicators_should_handle_zero_division_safely(self):
        indicators = AnalysisService.calculate_overview_indicators_by_messages([])

        assert indicators["total_messages"] == 0
        assert indicators["active_accounts"] == 0
        assert indicators["avg_latency"] == 0.0
        assert indicators["avg_of_conversation_messages"] == 0.0
        assert indicators["token_output_rate"] == 0.0
        assert indicators["cost_consumption"] == 0.0

    def test_calculate_pop_should_handle_previous_zero(self):
        current = {
            "total_messages": 10,
            "active_accounts": 3,
            "avg_of_conversation_messages": 2.5,
            "avg_latency": 6.0,
            "token_output_rate": 30.0,
            "cost_consumption": 6.0,
        }
        previous = {
            "total_messages": 5,
            "active_accounts": 0,
            "avg_of_conversation_messages": 2.0,
            "avg_latency": 3.0,
            "token_output_rate": 0.0,
            "cost_consumption": 3.0,
        }

        pop = AnalysisService.calculate_pop_by_overview_indicators(current, previous)

        assert pop["total_messages"] == pytest.approx(1.0)
        assert pop["active_accounts"] == 0.0
        assert pop["avg_of_conversation_messages"] == pytest.approx(0.25)
        assert pop["avg_latency"] == pytest.approx(1.0)
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

    @pytest.mark.parametrize("average", [1.25, None])
    def test_get_rag_latency_by_time_range_uses_persisted_retrieval_events(self, average):
        class _Query:
            def filter(self, *conditions):
                self.conditions = conditions
                return self

            def scalar(self):
                return average

        query = _Query()
        service = AnalysisService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args: query)),
            app_service=SimpleNamespace(),
        )
        app_id = uuid4()
        start_at = datetime(2024, 1, 1)
        end_at = datetime(2024, 1, 2)
        result = service.get_rag_latency_by_time_range(SimpleNamespace(id=app_id), start_at, end_at)

        assert result == average
        assert len(query.conditions) == 4
        assert [str(condition.left) for condition in query.conditions] == [
            "message_agent_thought.app_id",
            "message_agent_thought.event",
            "message_agent_thought.created_at",
            "message_agent_thought.created_at",
        ]
        assert [condition.operator for condition in query.conditions] == [
            operators.eq, operators.eq, operators.ge, operators.lt,
        ]
        assert [condition.right.value for condition in query.conditions] == [
            app_id, QueueEvent.DATASET_RETRIEVAL.value, start_at, end_at,
        ]

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
        expected_first_x = int(datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC).timestamp())
        assert trend["total_messages_trend"]["x_axis"][0] == expected_first_x
        assert trend["active_accounts_trend"]["x_axis"][0] == expected_first_x
        assert trend["avg_of_conversation_messages_trend"]["x_axis"][0] == expected_first_x
        assert trend["cost_consumption_trend"]["x_axis"][0] == expected_first_x

    def test_calculate_trend_by_messages_should_maintain_utc_x_axis_under_local_timezone(self):
        import os, time
        previous_tz = os.environ.get("TZ")
        os.environ["TZ"] = "Asia/Shanghai"
        time.tzset()
        try:
            end_at = datetime(2024, 1, 8, 18, 30, 0)
            trend = AnalysisService.calculate_trend_by_messages(end_at=end_at, days_ago=7, messages=[])
            expected_first_x = int(datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC).timestamp())
            assert trend["total_messages_trend"]["x_axis"][0] == expected_first_x
        finally:
            if previous_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = previous_tz
            time.tzset()

    def test_calculate_trend_by_messages_should_accept_aware_utc_datetimes(self, monkeypatch):
        monkeypatch.setattr(
            "internal.service.analysis_service.utc_now_naive",
            lambda: datetime(2024, 1, 8, 18, 30, 0),
        )
        end_at = datetime(2024, 1, 8, 18, 30, 0, tzinfo=UTC)
        messages = [
            _message(created_at=datetime(2024, 1, 2, 10, 0, 0, tzinfo=UTC), price=0.2),
            _message(created_at=datetime(2024, 1, 2, 11, 0, 0, tzinfo=UTC), price=0.4),
        ]

        trend = AnalysisService.calculate_trend_by_messages(end_at=end_at, days_ago=7, messages=messages)

        assert trend["total_messages_trend"]["y_axis"][0] == 2

    def test_get_rag_hit_rate_by_time_range_should_calculate_ratio(self):
        app = SimpleNamespace(id=uuid4())
        start_at = datetime(2024, 1, 1, 0, 0, 0)
        end_at = datetime(2024, 1, 8, 0, 0, 0)

        # 1. Total > 0
        service = _build_service(app=app)
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: SimpleNamespace(total=10, hits=8))
        )
        assert service.get_rag_hit_rate_by_time_range(app, start_at, end_at) == pytest.approx(0.8)

        # 2. Total == 0 -> None
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: SimpleNamespace(total=0, hits=0))
        )
        assert service.get_rag_hit_rate_by_time_range(app, start_at, end_at) is None

        # 3. None row -> None
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: None)
        )
        assert service.get_rag_hit_rate_by_time_range(app, start_at, end_at) is None

    def test_get_tool_call_success_rate_by_time_range_should_calculate_ratio(self):
        app = SimpleNamespace(id=uuid4())
        start_at = datetime(2024, 1, 1, 0, 0, 0)
        end_at = datetime(2024, 1, 8, 0, 0, 0)

        # 1. Total > 0
        service = _build_service(app=app)
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: SimpleNamespace(total=10, success_count=9))
        )
        assert service.get_tool_call_success_rate_by_time_range(app, start_at, end_at) == pytest.approx(0.9)

        # 2. Total == 0 -> None
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: SimpleNamespace(total=0, success_count=0))
        )
        assert service.get_tool_call_success_rate_by_time_range(app, start_at, end_at) is None

        # 3. None row -> None
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: None)
        )
        assert service.get_tool_call_success_rate_by_time_range(app, start_at, end_at) is None

    def test_get_rag_empty_result_rate_by_time_range_should_calculate_ratio(self):
        app = SimpleNamespace(id=uuid4())
        start_at = datetime(2024, 1, 1, 0, 0, 0)
        end_at = datetime(2024, 1, 8, 0, 0, 0)

        # 1. Total > 0
        service = _build_service(app=app)
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: SimpleNamespace(total=10, empty_count=3))
        )
        assert service.get_rag_empty_result_rate_by_time_range(app, start_at, end_at) == pytest.approx(0.3)

        # 2. Total == 0 -> None
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: SimpleNamespace(total=0, empty_count=0))
        )
        assert service.get_rag_empty_result_rate_by_time_range(app, start_at, end_at) is None

        # 3. None row -> None
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: None)
        )
        assert service.get_rag_empty_result_rate_by_time_range(app, start_at, end_at) is None

    def test_get_rag_failure_rate_by_time_range_should_calculate_ratio(self):
        app = SimpleNamespace(id=uuid4())
        start_at = datetime(2024, 1, 1, 0, 0, 0)
        end_at = datetime(2024, 1, 8, 0, 0, 0)

        # 1. Total > 0
        service = _build_service(app=app)
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: SimpleNamespace(total=10, failure_count=2))
        )
        assert service.get_rag_failure_rate_by_time_range(app, start_at, end_at) == pytest.approx(0.2)

        # 2. Total == 0 -> None
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: SimpleNamespace(total=0, failure_count=0))
        )
        assert service.get_rag_failure_rate_by_time_range(app, start_at, end_at) is None

        # 3. None row -> None
        service.db.session.query = lambda *_args: SimpleNamespace(
            filter=lambda *_f: SimpleNamespace(one_or_none=lambda: None)
        )
        assert service.get_rag_failure_rate_by_time_range(app, start_at, end_at) is None

    def test_get_rag_quality_summary_by_time_range(self, monkeypatch):
        app = SimpleNamespace(id=uuid4())
        start_at = datetime(2024, 1, 1, 0, 0, 0)
        end_at = datetime(2024, 1, 8, 0, 0, 0)
        service = _build_service(app=app)

        monkeypatch.setattr(service, "get_rag_hit_rate_by_time_range", lambda *_args: 0.8)
        monkeypatch.setattr(service, "get_rag_empty_result_rate_by_time_range", lambda *_args: 0.2)
        monkeypatch.setattr(service, "get_rag_failure_rate_by_time_range", lambda *_args: 0.05)
        monkeypatch.setattr(service, "get_rag_latency_by_time_range", lambda *_args: 1.25)

        summary = service.get_rag_quality_summary_by_time_range(app, start_at, end_at)
        assert summary == {
            "hit_rate": 0.8,
            "empty_result_rate": 0.2,
            "failure_rate": 0.05,
            "avg_latency": 1.25,
        }
