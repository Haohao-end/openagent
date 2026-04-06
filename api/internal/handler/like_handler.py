"""点赞列表 Handler"""
from dataclasses import dataclass

from flask import request
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required
from injector import inject

from internal.schema.like_schema import GetLikesReq
from internal.service.like_service import LikeService
from pkg.response import success_json, validate_error_json


@inject
@dataclass
class LikeHandler:
    """点赞列表 Handler"""

    like_service: LikeService

    @login_required
    def get_likes(self) -> ResponseReturnValue:
        """获取当前登录用户的点赞列表"""
        req = GetLikesReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        likes = self.like_service.get_likes(
            current_user,
            search_word=req.search_word.data,
            resource_type=req.resource_type.data,
        )
        return success_json(likes)
