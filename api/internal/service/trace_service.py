from internal.model import MessageAgentThought
from internal.extension.database_extension import db
from uuid import UUID
from typing import List

class TraceService:
    @staticmethod
    def get_message_timeline(app_id: UUID, message_id: UUID) -> List[MessageAgentThought]:
        return db.session.query(MessageAgentThought).filter(
            MessageAgentThought.app_id == app_id,
            MessageAgentThought.message_id == message_id
        ).order_by(MessageAgentThought.position.asc()).all()
