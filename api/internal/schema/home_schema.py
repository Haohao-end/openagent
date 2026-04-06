from marshmallow import Schema, fields


class SuggestedActionSchema(Schema):
    """推荐操作"""
    label = fields.String(required=True)
    action = fields.String(required=True)
    icon = fields.String(required=True)


class GetIntentResp(Schema):
    """获取意图识别结果响应"""
    intent = fields.String(dump_default="")
    confidence = fields.Float(dump_default=0.0)
    suggested_actions = fields.List(fields.Nested(SuggestedActionSchema), dump_default=[])
    is_default = fields.Boolean(dump_default=False)
