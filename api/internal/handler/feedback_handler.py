from flask import request
from flask_login import current_user
from internal.schema.feedback_schema import FeedbackCreateReq
from internal.service.feedback_service import FeedbackService
from internal.model import App
from internal.extension.database_extension import db
from uuid import UUID

class FeedbackHandler:
    @staticmethod
    def create_feedback(app_id: UUID):
        app = db.session.query(App).filter(App.id == app_id, App.account_id == current_user.id).first()
        if not app:
            return {"error": "App not found"}, 404
        req = FeedbackCreateReq(data=request.get_json())
        if not req.validate():
            return {"error": f"Invalid request: {req.errors}"}, 400
        feedback = FeedbackService.create_feedback(app, req, current_user.id)
        return {"id": feedback.id}, 201
