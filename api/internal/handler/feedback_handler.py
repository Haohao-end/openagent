from uuid import UUID
from flask import request
from flask_login import current_user
from internal.exception import NotFoundException
from internal.extension.database_extension import db
from internal.model import App
from internal.schema.feedback_schema import FeedbackCreateReq, FeedbackListReq
from internal.service.feedback_service import FeedbackService


class FeedbackHandler:
    @staticmethod
    def create_feedback(app_id: UUID):
        app = db.session.query(App).filter(App.id == app_id, App.account_id == current_user.id).first()
        if not app:
            return {"error": "App not found"}, 404
        req = FeedbackCreateReq(data=request.get_json())
        if not req.validate():
            return {"error": f"Invalid request: {req.errors}"}, 400
        try:
            feedback = FeedbackService.create_feedback(app, req, current_user.id)
            return {"id": feedback.id}, 201
        except NotFoundException as exc:
            return {"error": exc.message if hasattr(exc, "message") else str(exc)}, 404
        except ValueError as exc:
            return {"error": str(exc)}, 400

    @staticmethod
    def get_feedbacks(app_id: UUID):
        app = db.session.query(App).filter(App.id == app_id, App.account_id == current_user.id).first()
        if not app:
            return {"error": "App not found"}, 404
        req = FeedbackListReq(request.args)
        if not req.validate():
            return {"error": f"Invalid request: {req.errors}"}, 400

        feedbacks = FeedbackService.get_feedbacks(
            app.id,
            req.target_type.data,
            req.page.data or 1,
            req.limit.data or 20,
        )
        return {
            "data": [
                {
                    "id": f.id,
                    "target_id": f.target_id,
                    "target_type": f.target_type,
                    "rating": f.rating,
                    "content": f.content,
                }
                for f in feedbacks
            ]
        }, 200
