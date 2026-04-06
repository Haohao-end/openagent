from marshmallow import Schema, fields


class DocumentIndexNotificationSchema(Schema):
    """文档索引完成通知序列化模式"""
    id = fields.String(required=True)
    user_id = fields.UUID(required=True)
    dataset_id = fields.UUID(required=True)
    document_id = fields.UUID(required=True)
    document_name = fields.String(required=True)
    segment_count = fields.Integer(required=True)
    index_duration = fields.Float(required=True)
    created_at = fields.DateTime(required=True)
    status = fields.String(required=True)  # success 或 error
    error_message = fields.String(required=False)
    is_read = fields.Boolean(required=True)
