from dataclasses import dataclass
from injector import inject
from flask import g
from flask_login import login_required, logout_user, current_user
from pkg.response import success_message, validate_error_json, success_json
from internal.schema.auth_schema import (
    PasswordLoginResp,
    PasswordLoginReq,
    PrepareRegisterReq,
    VerifyRegisterReq,
    SendResetCodeReq,
    ResetPasswordReq,
    VerifyLoginChallengeReq,
    ResendLoginChallengeReq,
)
from internal.service import AccountService

@inject
@dataclass
class AuthHandler:
    """OpenAgent 平台自有授权认证处理器"""
    account_service: AccountService

    def password_login(self):
        """账号密码登陆"""
        # 1.提取请求并校验数据
        req = PasswordLoginReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务登陆账号
        credential = self.account_service.password_login(req.email.data, req.password.data)

        # 3.创建响应结构并返回
        resp = PasswordLoginResp()

        return success_json(resp.dump(credential))

    def prepare_register(self):
        """发送注册验证码"""
        req = PrepareRegisterReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.account_service.prepare_register(req.email.data, req.password.data)
        return success_message("验证码已发送到您的邮箱,请查收")

    def verify_register(self):
        """校验注册验证码并创建账号"""
        req = VerifyRegisterReq()
        if not req.validate():
            return validate_error_json(req.errors)

        credential = self.account_service.register_by_email_code(
            req.email.data,
            req.password.data,
            req.code.data,
        )

        resp = PasswordLoginResp()
        return success_json(resp.dump(credential))

    @login_required
    def logout(self):
        """退出登陆 用于提示前端清除授权凭证"""
        current_session = getattr(g, "current_account_session", None)
        if current_session is not None:
            self.account_service.revoke_account_session(
                current_user,
                current_session.id,
                current_session_id=current_session.id,
                allow_current=True,
            )
        logout_user()
        return success_message("退出登陆成功")

    def send_reset_code(self):
        """发送密码重置验证码"""
        # 1.提取请求并校验数据
        req = SendResetCodeReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务发送验证码
        self.account_service.send_reset_code(req.email.data)

        return success_message("如果该邮箱已注册，验证码已发送，请查收")

    def reset_password(self):
        """重置密码"""
        # 1.提取请求并校验数据
        req = ResetPasswordReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务重置密码
        self.account_service.reset_password(
            req.email.data,
            req.code.data,
            req.new_password.data
        )

        return success_message("密码重置成功,请使用新密码登录")

    def verify_login_challenge(self):
        """完成异常登录的二次验证码校验。"""
        req = VerifyLoginChallengeReq()
        if not req.validate():
            return validate_error_json(req.errors)

        credential = self.account_service.verify_login_challenge(
            req.challenge_id.data,
            req.code.data,
        )

        resp = PasswordLoginResp()
        return success_json(resp.dump(credential))

    def resend_login_challenge(self):
        """重发异常登录的二次验证码。"""
        req = ResendLoginChallengeReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.account_service.resend_login_challenge(req.challenge_id.data)

        return success_message("验证码已发送到您的邮箱,请查收")
