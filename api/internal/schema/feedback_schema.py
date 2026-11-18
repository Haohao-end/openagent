from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Optional, AnyOf

class FeedbackCreateReq(FlaskForm):
    target_id = StringField('target_id', validators=[DataRequired()])
    target_type = StringField('target_type', validators=[DataRequired(), AnyOf(['message', 'span'])])
    rating = IntegerField('rating', validators=[Optional(), AnyOf([-1, 1])])
    content = TextAreaField('content', validators=[Optional()])

class FeedbackListReq(FlaskForm):
    app_id = StringField('app_id', validators=[DataRequired()])
    target_type = StringField('target_type', validators=[Optional(), AnyOf(['message', 'span'])])
    page = IntegerField('page', validators=[Optional()])
    limit = IntegerField('limit', validators=[Optional()])
