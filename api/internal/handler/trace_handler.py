from flask_login import current_user
from internal.service.trace_service import TraceService
from internal.model import App
from internal.extension.database_extension import db
from uuid import UUID

class TraceHandler:
    @staticmethod
    def get_message_timeline(app_id: UUID, message_id: UUID):
        app = db.session.query(App).filter(App.id == app_id, App.account_id == current_user.id).first()
        if not app:
            return {"error": "App not found"}, 404
        timeline = TraceService.get_message_timeline(app_id, message_id)
        return [{"id": t.id, "thought": t.thought, "observation": t.observation, "tool": t.tool, "latency": t.latency} for t in timeline], 200
