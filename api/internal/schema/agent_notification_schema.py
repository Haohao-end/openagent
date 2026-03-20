from marshmallow import Schema, fields


class AgentNotificationSchema(Schema):
    """Agent通知Schema"""
    id = fields.String(required=True)
    user_id = fields.UUID(required=True)
    app_id = fields.UUID(required=True)
    app_name = fields.String(required=True)
    created_at = fields.DateTime(required=True)
    is_read = fields.Boolean(required=True)
