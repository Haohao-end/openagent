"""公共应用Handler - 处理HTTP请求"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import current_user, login_required
from injector import inject

from pkg.response import success_json, success_message, validate_error_json, compact_generate_response
from internal.schema.public_app_schema import (
    ShareAppToSquareReq,
    GetPublicAppsWithPageReq,
    PublicAppResp,
    GetAppCategoriesResp,
    LikeAppResp,
    FavoriteAppResp,
    ForkAppResp,
)
from internal.service.public_app_service import PublicAppService
from internal.service.analysis_service import AnalysisService
from pkg.paginator import PageModel


@inject
@dataclass
class PublicAppHandler:
    """公共应用Handler"""
    public_app_service: PublicAppService
    analysis_service: AnalysisService

    @login_required
    def share_app_to_square(self, app_id: UUID):
        """共享应用到广场"""
        # 1.提取并校验请求数据
        req = ShareAppToSquareReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务共享应用
        self.public_app_service.share_app_to_square(app_id, req.category.data, current_user)

        return success_message("应用已共享到广场")

    @login_required
    def unshare_app_from_square(self, app_id: UUID):
        """取消应用从广场的共享"""
        self.public_app_service.unshare_app_from_square(app_id, current_user)
        return success_message("应用已从广场取消共享")

    def get_public_apps_with_page(self):
        """获取公共应用广场列表(支持未登录访问)"""
        # 1.提取并校验请求数据
        req = GetPublicAppsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务获取列表(如果用户已登录则传入current_user,否则传None)
        try:
            account = current_user if current_user.is_authenticated else None
        except:
            account = None

        apps, paginator = self.public_app_service.get_public_apps_with_page(req, account)

        # 3.返回响应
        return success_json(PageModel(list=apps, paginator=paginator))

    def get_app_categories(self):
        """获取应用分类列表"""
        resp = GetAppCategoriesResp()
        return success_json(resp.dump({}))

    @login_required
    def fork_public_app(self, app_id: str):
        """Fork公共应用到个人空间"""
        app = self.public_app_service.fork_public_app(app_id, current_user)
        resp = ForkAppResp()
        return success_json(resp.dump({"id": str(app.id), "name": app.name}))

    @login_required
    def like_app(self, app_id: UUID):
        """点赞/取消点赞应用"""
        result = self.public_app_service.like_app(app_id, current_user)
        resp = LikeAppResp()
        return success_json(resp.dump(result))

    @login_required
    def favorite_app(self, app_id: UUID):
        """收藏/取消收藏应用"""
        result = self.public_app_service.favorite_app(app_id, current_user)
        resp = FavoriteAppResp()
        return success_json(resp.dump(result))

    @login_required
    def get_my_favorites(self):
        """获取我的收藏列表"""
        apps = self.public_app_service.get_my_favorites(current_user)
        resp = PublicAppResp(many=True)
        return success_json(resp.dump(apps))

    def get_public_app_detail(self, app_id: str):
        """获取公共应用详情（支持未登录访问）"""
        # 1.判断用户是否登录
        try:
            account = current_user if current_user.is_authenticated else None
        except:
            account = None

        # 2.获取应用详情
        app_detail = self.public_app_service.get_public_app_detail(app_id, account)

        # 3.返回响应
        return success_json(app_detail)

    def get_public_app_analysis(self, app_id: str):
        """获取公共应用的统计分析数据（支持未登录访问）"""
        # 1.判断用户是否登录
        try:
            account = current_user if current_user.is_authenticated else None
        except:
            account = None

        # 2.获取应用统计分析数据
        app_analysis = self.public_app_service.get_public_app_analysis(app_id, account)

        # 3.返回响应
        return success_json(app_analysis)
