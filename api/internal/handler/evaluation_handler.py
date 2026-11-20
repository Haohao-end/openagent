from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required
from injector import inject

from internal.schema.evaluation_schema import CreateEvaluationReq, GetEvaluationsReq
from internal.service.evaluation_service import EvaluationService
from pkg.response import success_json, validate_error_json


@inject
@dataclass
class EvaluationHandler:
    evaluation_service: EvaluationService

    @login_required
    def get_evaluations(self, app_id: UUID) -> ResponseReturnValue:
        """获取应用下的评测集列表"""
        req = GetEvaluationsReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        evaluations = self.evaluation_service.get_evaluations(app_id, req, current_user)
        return success_json(evaluations)

    @login_required
    def create_evaluation(self, app_id: UUID) -> ResponseReturnValue:
        """为指定应用创建评测集"""
        req = CreateEvaluationReq(data=request.get_json())
        if not req.validate():
            return validate_error_json(req.errors)

        evaluation = self.evaluation_service.create_evaluation(app_id, req, current_user)
        return success_json(evaluation)
