from dataclasses import dataclass

from flask_login import login_required, current_user
from injector import inject

from internal.schema.home_schema import GetIntentResp
from internal.service import HomeService
from pkg.response import success_json


@inject
@dataclass
class HomeHandler:
    """首页处理器"""
    home_service: HomeService

    @login_required
    def get_intent(self):
        """获取用户的意图识别结果"""
        # 1. 调用服务获取意图
        intent_result = self.home_service.get_user_intent(current_user)

        # 2. 构建响应结构并返回
        resp = GetIntentResp()
        return success_json(resp.dump(intent_result))
