from types import SimpleNamespace
from uuid import uuid4
import json

from internal.handler.analysis_handler import AnalysisHandler


class TestAnalysisHandler:
    def test_get_app_analysis_should_return_success_json(self, app, monkeypatch):
        """测试获取应用统计分析返回成功响应"""
        app_id = uuid4()
        account = SimpleNamespace(id=uuid4())
        analysis_data = {
            "total_messages": {"data": 100, "pop": 0.2},
            "active_accounts": {"data": 10, "pop": 0.1},
            "total_messages_trend": {"x_axis": [], "y_axis": []},
        }

        analysis_service = SimpleNamespace(
            get_app_analysis=lambda aid, acc: analysis_data
        )
        handler = AnalysisHandler(analysis_service=analysis_service)

        # Mock current_user
        monkeypatch.setattr("internal.handler.analysis_handler.current_user", account)

        with app.test_request_context("/analysis"):
            response_tuple = handler.get_app_analysis(app_id)

            # success_json returns (response, status_code)
            response, status_code = response_tuple
            data = json.loads(response.get_data(as_text=True))

            assert status_code == 200
            assert data["code"] == "success"
            assert data["data"] == analysis_data
