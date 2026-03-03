from dataclasses import dataclass
from injector import inject
from flask_login import login_required, current_user
from internal.schema.account_schema import (
    GetCurrentUserResp,
    UpdatePasswordReq,
    UpdateNameReq,
    UpdateAvatarReq
)
from pkg.response import success_json, validate_error_json, success_message
from internal.service import AccountService

@inject
@dataclass
class AccountHandler:
    """账号设置处理器"""
    account_service: AccountService

    @login_required
    def get_current_user(self):
        """获取当前登陆账号信息"""
        resp = GetCurrentUserResp()
        return success_json(resp.dump(current_user))
        
    @login_required
    def update_password(self):
        """更新当前登陆账号密码"""
        # 1.提取请求数据并校验
        req = UpdatePasswordReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务更新账号密码
        self.account_service.update_password(req.password.data, current_user)

        return success_message("更新账号密码成功")

    @login_required
    def update_name(self):
        """更新当前登陆账号名称"""
        # 1.提取请求数据并校验
        req = UpdateNameReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务更新账号名称
        self.account_service.update_account(current_user, name=req.name.data)

        return success_message("更新账号名称成功")

    @login_required
    def update_avatar(self):
        """更新当前账号头像信息"""
        # 1.提取请求数据并校验
        req = UpdateAvatarReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务更新账号头像
        self.account_service.update_account(current_user, avatar=req.avatar.data)

        return success_message("更新账号头像成功")
