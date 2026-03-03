from dataclasses import dataclass
from uuid import UUID

from injector import inject

from internal.service import WechatService


@inject
@dataclass
class WechatHandler:
    """微信公众号服务服务"""
    wechat_service: WechatService

    def wechat(self, app_id: UUID):
        """Agent微信API校验与消息推送"""
        return self.wechat_service.wechat(app_id)
