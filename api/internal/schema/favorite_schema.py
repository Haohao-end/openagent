"""收藏列表请求参数 Schema"""
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import AnyOf, Length, Optional


class GetFavoritesReq(FlaskForm):
    """获取收藏列表请求"""

    search_word = StringField("search_word", default="", validators=[Optional(), Length(max=255)])
    resource_type = StringField(
        "resource_type",
        default="all",
        validators=[Optional(), AnyOf(["all", "app", "workflow"])],
    )
