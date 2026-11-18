from uuid import UUID
from typing import Any, List, Optional
from internal.model import Feedback, App, Message
from internal.extension.database_extension import db
from sqlalchemy import desc

class FeedbackService:
    @staticmethod
    def create_feedback(app: App, req: Any, account_id: UUID) -> Feedback:
        target_id = UUID(req.target_id)
        # Verify message existence and ownership
        msg = db.session.query(Message).filter(Message.id == target_id, Message.app_id == app.id).first()
        if not msg:
            raise ValueError("Invalid target_id or access denied")
        
        feedback = Feedback(
            app_id=app.id,
            conversation_id=msg.conversation_id,
            target_id=target_id,
            target_type=req.target_type,
            rating=req.rating,
            content=req.content,
            created_by=account_id
        )
        db.session.add(feedback)
        db.session.commit()
        return feedback

    @staticmethod
    def get_feedbacks(app_id: UUID, target_type: Optional[str], page: int, limit: int) -> List[Feedback]:
        query = db.session.query(Feedback).filter(Feedback.app_id == app_id)
        if target_type:
            query = query.filter(Feedback.target_type == target_type)
        return query.order_by(desc(Feedback.created_at)).offset((page - 1) * limit).limit(limit).all()
