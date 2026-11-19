from uuid import UUID
from flask_login import current_user
from internal.extension.database_extension import db
from internal.model import App, Message
from internal.service.trace_service import TraceService


class TraceHandler:
    @staticmethod
    def get_message_timeline(app_id: UUID, message_id: UUID):
        if not current_user or not getattr(current_user, "is_authenticated", False):
            return {"error": "Unauthorized"}, 401
        app = db.session.query(App).filter(App.id == app_id, App.account_id == current_user.id).first()
        if not app:
            return {"error": "App not found"}, 404
        message = db.session.query(Message).filter(Message.id == message_id, Message.app_id == app_id).first()
        if not message:
            return {"error": "Message not found"}, 404
        timeline = TraceService.get_message_timeline(app_id, message_id)
        return [{"id": t.id, "thought": t.thought, "observation": t.observation, "tool": t.tool, "latency": t.latency} for t in timeline], 200
