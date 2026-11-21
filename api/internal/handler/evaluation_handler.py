from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required
from injector import inject

from internal.schema.evaluation_schema import (
    CreateEvaluationCaseReq,
    CreateEvaluationReq,
    GetEvaluationCasesReq,
    GetEvaluationsReq,
    UpdateEvaluationCaseReq,
    UpdateEvaluationReq,
)
from internal.service.evaluation_service import EvaluationService
from pkg.response import success_json, validate_error_json


def _json_payload() -> dict:
    """非 JSON/非对象请求体统一按空字典处理，交给 schema 返回校验错误。"""
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


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
        req = CreateEvaluationReq(formdata=None, data=_json_payload())
        if not req.validate():
            return validate_error_json(req.errors)

        evaluation = self.evaluation_service.create_evaluation(app_id, req, current_user)
        return success_json(evaluation)

    @login_required
    def get_evaluation(self, app_id: UUID, evaluation_id: UUID) -> ResponseReturnValue:
        """获取单个评测集详情"""
        evaluation = self.evaluation_service.get_evaluation(app_id, evaluation_id, current_user)
        return success_json(evaluation)

    @login_required
    def update_evaluation(self, app_id: UUID, evaluation_id: UUID) -> ResponseReturnValue:
        """更新评测集名称"""
        req = UpdateEvaluationReq(formdata=None, data=_json_payload())
        if not req.validate():
            return validate_error_json(req.errors)

        evaluation = self.evaluation_service.update_evaluation(app_id, evaluation_id, req, current_user)
        return success_json(evaluation)

    @login_required
    def delete_evaluation(self, app_id: UUID, evaluation_id: UUID) -> ResponseReturnValue:
        """删除评测集"""
        result = self.evaluation_service.delete_evaluation(app_id, evaluation_id, current_user)
        return success_json(result)

    @login_required
    def get_evaluation_cases(self, app_id: UUID, evaluation_id: UUID) -> ResponseReturnValue:
        """获取评测集下的用例列表"""
        req = GetEvaluationCasesReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        cases = self.evaluation_service.get_evaluation_cases(app_id, evaluation_id, req, current_user)
        return success_json(cases)

    @login_required
    def create_evaluation_case(self, app_id: UUID, evaluation_id: UUID) -> ResponseReturnValue:
        """为评测集创建测试用例"""
        req = CreateEvaluationCaseReq(formdata=None, data=_json_payload())
        if not req.validate():
            return validate_error_json(req.errors)

        case = self.evaluation_service.create_evaluation_case(app_id, evaluation_id, req, current_user)
        return success_json(case)

    @login_required
    def get_evaluation_case(
        self, app_id: UUID, evaluation_id: UUID, case_id: UUID
    ) -> ResponseReturnValue:
        """获取单个评测用例详情"""
        case = self.evaluation_service.get_evaluation_case(app_id, evaluation_id, case_id, current_user)
        return success_json(case)

    @login_required
    def update_evaluation_case(
        self, app_id: UUID, evaluation_id: UUID, case_id: UUID
    ) -> ResponseReturnValue:
        """更新单个评测用例"""
        req = UpdateEvaluationCaseReq(formdata=None, data=_json_payload())
        if not req.validate():
            return validate_error_json(req.errors)

        case = self.evaluation_service.update_evaluation_case(
            app_id, evaluation_id, case_id, req, current_user
        )
        return success_json(case)

    @login_required
    def delete_evaluation_case(
        self, app_id: UUID, evaluation_id: UUID, case_id: UUID
    ) -> ResponseReturnValue:
        """删除单个评测用例"""
        result = self.evaluation_service.delete_evaluation_case(
            app_id, evaluation_id, case_id, current_user
        )
        return success_json(result)
