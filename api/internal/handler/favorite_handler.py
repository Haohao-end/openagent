"""收藏列表 Handler"""
from dataclasses import dataclass

from flask import request
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required
from injector import inject

from internal.schema.favorite_schema import GetFavoritesReq
from internal.service.favorite_service import FavoriteService
from pkg.response import success_json, validate_error_json


@inject
@dataclass
class FavoriteHandler:
    """收藏列表 Handler"""

    favorite_service: FavoriteService

    @login_required
    def get_favorites(self) -> ResponseReturnValue:
        """获取当前登录用户的收藏列表"""
        req = GetFavoritesReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        favorites = self.favorite_service.get_favorites(
            current_user,
            search_word=req.search_word.data,
            resource_type=req.resource_type.data,
        )
        return success_json(favorites)
