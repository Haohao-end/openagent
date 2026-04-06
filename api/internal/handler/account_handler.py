from dataclasses import dataclass
from injector import inject
from flask import g, request
from flask_login import login_required, current_user
from internal.schema.account_schema import (
    GetAccountLoginHistoryReq,
    GetAccountLoginHistoryResp,
    GetAccountSessionsResp,
    GetCurrentUserResp,
    SendChangeEmailCodeReq,
    UpdateEmailReq,
    UpdatePasswordReq,
    UpdateNameReq,
    UpdateAvatarReq
)
from pkg.response import success_json, validate_error_json, success_message
from internal.service import AccountService, OAuthService

@inject
@dataclass
class AccountHandler:
    """账号设置处理器"""
    account_service: AccountService
    oauth_service: OAuthService

    @login_required
    def get_current_user(self):
        """获取当前登陆账号信息"""
        resp = GetCurrentUserResp()
        return success_json(resp.dump({
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "avatar": current_user.avatar,
            "last_login_at": current_user.last_login_at,
            "last_login_ip": current_user.last_login_ip,
            "last_login_location": self.account_service.resolve_ip_location(current_user.last_login_ip),
            "created_at": current_user.created_at,
            "password_set": current_user.is_password_set,
            "oauth_bindings": self.account_service.get_account_oauth_bindings(current_user),
        }))

    @login_required
    def update_password(self):
        """更新当前登陆账号密码"""
        # 1.提取请求数据并校验
        req = UpdatePasswordReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务更新账号密码
        self.account_service.change_password(
            current_user,
            req.current_password.data,
            req.new_password.data,
        )

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

    @login_required
    def send_change_email_code(self):
        """向新邮箱发送换绑验证码。"""
        req = SendChangeEmailCodeReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.account_service.send_change_email_code(current_user, req.email.data)
        return success_message("验证码已发送到新邮箱,请查收")

    @login_required
    def update_email(self):
        """更新当前账号绑定邮箱。"""
        req = UpdateEmailReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.account_service.update_email(
            current_user,
            req.email.data,
            req.code.data,
            req.current_password.data,
        )
        return success_message("绑定邮箱更新成功")

    @login_required
    def get_account_sessions(self):
        """获取当前账号登录设备/会话列表。"""
        current_session = getattr(g, "current_account_session", None)
        resp = GetAccountSessionsResp()
        return success_json(resp.dump({
            "session_capable": current_session is not None,
            "current_session_id": getattr(current_session, "id", None),
            "sessions": self.account_service.get_account_sessions(
                current_user,
                getattr(current_session, "id", None),
            ),
        }))

    @login_required
    def get_account_login_history(self):
        """获取当前账号最近的登录历史。"""
        req = GetAccountLoginHistoryReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        current_session = getattr(g, "current_account_session", None)
        resp = GetAccountLoginHistoryResp()
        return success_json(resp.dump(self.account_service.get_account_login_history(
            current_user,
            getattr(current_session, "id", None),
            status=req.status.data,
            search=req.search.data,
            current_page=req.current_page.data,
            page_size=req.page_size.data,
        )))

    @login_required
    def revoke_account_session(self, session_id):
        """撤销指定登录会话。"""
        current_session = getattr(g, "current_account_session", None)
        self.account_service.revoke_account_session(
            current_user,
            session_id,
            current_session_id=getattr(current_session, "id", None),
        )
        return success_message("登录设备已下线")

    @login_required
    def revoke_other_account_sessions(self):
        """撤销除当前设备外的所有登录会话。"""
        current_session = getattr(g, "current_account_session", None)
        self.account_service.revoke_other_account_sessions(
            current_user,
            getattr(current_session, "id", None),
        )
        return success_message("其他登录设备已全部下线")

    @login_required
    def unbind_oauth(self, provider_name: str):
        """解绑当前账号的第三方登录方式"""
        self.oauth_service.unbind_oauth(current_user, provider_name)
        return success_message("解绑第三方账号成功")
