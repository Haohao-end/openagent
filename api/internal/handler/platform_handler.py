from dataclasses import dataclass
from uuid import UUID

from flask_login import login_required, current_user
from injector import inject

from internal.schema.platform_schema import GetWechatConfigResp, UpdateWechatConfigReq
from internal.service import PlatformService
from pkg.response import success_json, validate_error_json, success_message


@inject
@dataclass
class PlatformHandler:
    """第三方平台处理器"""
    platform_service: PlatformService

    @login_required
    def get_wechat_config(self, app_id: UUID):
        """根据传递的id获取指定应用的微信配置"""
        # 1.调用服务获取应用的微信公众号配置
        wechat_config = self.platform_service.get_wechat_config(app_id, current_user)

        # 2.构建响应并返回
        resp = GetWechatConfigResp()

        return success_json(resp.dump(wechat_config))

    @login_required
    def update_wechat_config(self, app_id: UUID):
        """根据传递的应用id更新该应用的微信发布配置"""
        # 1.提取请求并校验
        req = UpdateWechatConfigReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务并更新应用配置
        self.platform_service.update_wechat_config(app_id, req, current_user)

        return success_message("更新Agent应用微信公众号配置成功")
