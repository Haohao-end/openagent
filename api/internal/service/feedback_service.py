from uuid import UUID
from typing import Any, List, Optional
from internal.exception import NotFoundException
from internal.extension.database_extension import db
from internal.model import Feedback, App, Message, MessageAgentThought
from sqlalchemy import desc


class FeedbackService:
    @staticmethod
    def create_feedback(app: App, req: Any, account_id: UUID) -> Feedback:
        target_id = UUID(req.target_id.data)
        target_type = req.target_type.data

        # Verify target existence and ownership
        if target_type == "message":
            msg = db.session.query(Message).filter(Message.id == target_id, Message.app_id == app.id).first()
            if not msg:
                raise NotFoundException("Message not found or access denied")
            conversation_id = msg.conversation_id
        elif target_type == "span":
            thought = db.session.query(MessageAgentThought).filter(
                MessageAgentThought.id == target_id,
                MessageAgentThought.app_id == app.id,
            ).first()
            if not thought:
                raise NotFoundException("Span not found or access denied")
            conversation_id = thought.conversation_id
        else:
            raise ValueError("Invalid target_type")

        feedback = Feedback(
            app_id=app.id,
            conversation_id=conversation_id,
            target_id=target_id,
            target_type=target_type,
            rating=req.rating.data,
            content=req.content.data,
            created_by=account_id,
        )
        db.session.add(feedback)
        db.session.commit()
        return feedback

    @staticmethod
    def get_feedbacks(app_id: UUID, target_type: Optional[str], page: int, limit: int) -> List[Feedback]:
        query = db.session.query(Feedback).filter(Feedback.app_id == app_id)
        if target_type:
            query = query.filter(Feedback.target_type == target_type)
        return query.order_by(desc(Feedback.created_at), desc(Feedback.id)).offset((page - 1) * limit).limit(limit).all()
