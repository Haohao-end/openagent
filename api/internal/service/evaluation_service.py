from dataclasses import dataclass
from uuid import UUID

from injector import inject
from sqlalchemy import desc

from internal.exception import FailException, NotFoundException, ValidateErrorException
from internal.lib.helper import datetime_to_timestamp
from internal.model import Account, App, Evaluation, EvaluationCase
from internal.schema.evaluation_schema import CreateEvaluationReq, GetEvaluationsReq, UpdateEvaluationReq
from internal.service.base_service import BaseService
from pkg.sqlalchemy import SQLAlchemy


@inject
@dataclass
class EvaluationService(BaseService):
    db: SQLAlchemy

    def get_evaluations(self, app_id: UUID, req: GetEvaluationsReq, account: Account) -> list[dict]:
        """获取应用下的评测集列表"""
        app = self.get(App, app_id)
        if not app or app.account_id != account.id:
            raise NotFoundException("该应用不存在")

        page = req.page.data or 1
        limit = req.limit.data or 20
        evaluations = (
            self.db.session.query(Evaluation)
            .filter(Evaluation.app_id == app_id)
            .order_by(desc(Evaluation.created_at), desc(Evaluation.id))
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": str(e.id),
                "app_id": str(e.app_id),
                "name": e.name,
                "created_by": str(e.created_by),
                "created_at": datetime_to_timestamp(e.created_at),
                "updated_at": datetime_to_timestamp(e.updated_at),
            }
            for e in evaluations
        ]

    def create_evaluation(self, app_id: UUID, req: CreateEvaluationReq, account: Account) -> dict:
        """为指定应用创建评测集"""
        app = self.get(App, app_id)
        if not app or app.account_id != account.id:
            raise NotFoundException("该应用不存在")

        name = (req.name.data or "").strip()
        if not name:
            raise ValidateErrorException("评测集名称不能为空")

        evaluation = Evaluation(
            app_id=app_id,
            name=name,
            created_by=account.id,
        )
        try:
            self.db.session.add(evaluation)
            self.db.session.commit()
        except Exception:
            self.db.session.rollback()
            raise FailException("创建评测集失败，请稍后重试")

        return {
            "id": str(evaluation.id),
            "app_id": str(evaluation.app_id),
            "name": evaluation.name,
            "created_by": str(evaluation.created_by),
            "created_at": datetime_to_timestamp(evaluation.created_at),
            "updated_at": datetime_to_timestamp(evaluation.updated_at),
        }

    def get_evaluation(self, app_id: UUID, evaluation_id: UUID, account: Account) -> dict:
        """获取单个评测集详情"""
        app = self.get(App, app_id)
        if not app or app.account_id != account.id:
            raise NotFoundException("该应用不存在")

        evaluation = (
            self.db.session.query(Evaluation)
            .filter(Evaluation.id == evaluation_id, Evaluation.app_id == app_id)
            .first()
        )
        if not evaluation:
            raise NotFoundException("该评测集不存在")

        return {
            "id": str(evaluation.id),
            "app_id": str(evaluation.app_id),
            "name": evaluation.name,
            "created_by": str(evaluation.created_by),
            "created_at": datetime_to_timestamp(evaluation.created_at),
            "updated_at": datetime_to_timestamp(evaluation.updated_at),
        }

    def update_evaluation(self, app_id: UUID, evaluation_id: UUID, req: UpdateEvaluationReq, account: Account) -> dict:
        """更新评测集名称"""
        app = self.get(App, app_id)
        if not app or app.account_id != account.id:
            raise NotFoundException("该应用不存在")

        evaluation = (
            self.db.session.query(Evaluation)
            .filter(Evaluation.id == evaluation_id, Evaluation.app_id == app_id)
            .first()
        )
        if not evaluation:
            raise NotFoundException("该评测集不存在")

        name = (req.name.data or "").strip()
        if not name:
            raise ValidateErrorException("评测集名称不能为空")

        evaluation.name = name
        try:
            self.db.session.commit()
        except Exception:
            self.db.session.rollback()
            raise FailException("更新评测集失败，请稍后重试")

        return {
            "id": str(evaluation.id),
            "app_id": str(evaluation.app_id),
            "name": evaluation.name,
            "created_by": str(evaluation.created_by),
            "created_at": datetime_to_timestamp(evaluation.created_at),
            "updated_at": datetime_to_timestamp(evaluation.updated_at),
        }

    def delete_evaluation(self, app_id: UUID, evaluation_id: UUID, account: Account) -> dict:
        """删除评测集及关联用例"""
        app = self.get(App, app_id)
        if not app or app.account_id != account.id:
            raise NotFoundException("该应用不存在")

        evaluation = (
            self.db.session.query(Evaluation)
            .filter(Evaluation.id == evaluation_id, Evaluation.app_id == app_id)
            .first()
        )
        if not evaluation:
            raise NotFoundException("该评测集不存在")

        try:
            self.db.session.query(EvaluationCase).filter(EvaluationCase.evaluation_id == evaluation.id).delete()
            self.db.session.delete(evaluation)
            self.db.session.commit()
        except Exception:
            self.db.session.rollback()
            raise FailException("删除评测集失败，请稍后重试")

        return {"id": str(evaluation_id)}
