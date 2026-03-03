from dataclasses import dataclass
from injector import inject
from uuid import UUID
from internal.service import AnalysisService
from pkg.response import success_json
from flask_login import current_user, login_required


@inject
@dataclass
class AnalysisHandler:
    """统计分析处理器"""
    analysis_service: AnalysisService

    @login_required
    def get_app_analysis(self, app_id: UUID):
        """根据传递的应用id获取应用的统计信息"""
        app_analysis = self.analysis_service.get_app_analysis(app_id, current_user)
        return success_json(app_analysis)
