from dataclasses import dataclass
from datetime import timedelta
import secrets
import string

from injector import inject
from flask import current_app, has_request_context, request
from flask_mail import Mail, Message

from internal.exception import FailException
from internal.extension.redis_extension import redis_client
from internal.task.email_task import send_verification_email_task


@inject
@dataclass
class EmailService:
    """邮件服务"""
    mail: Mail
    PASSWORD_RESET_SCENE = "password_reset"
    CHANGE_EMAIL_SCENE = "change_email"
    LOGIN_CHALLENGE_SCENE = "login_challenge"
    REGISTER_SCENE = "register"
    CODE_TTL_SECONDS = 5 * 60
    SEND_COOLDOWN_SECONDS = 60
    SEND_WINDOW_SECONDS = 60 * 60
    MAX_SEND_COUNT_PER_WINDOW = 10
    MAX_SEND_COUNT_PER_IP_PER_WINDOW = 30
    MAX_VERIFY_ATTEMPTS = 5
    VERIFY_LOCK_SECONDS = 15 * 60
    SEND_PENDING_SECONDS = 2 * 60

    @classmethod
    def _code_key(cls, email: str, scene: str = PASSWORD_RESET_SCENE) -> str:
        return f"{scene}:{email}"

    @classmethod
    def _send_count_key(cls, email: str, scene: str = PASSWORD_RESET_SCENE) -> str:
        return f"{scene}:send_count:{email}"

    @classmethod
    def _send_cooldown_key(cls, email: str, scene: str = PASSWORD_RESET_SCENE) -> str:
        return f"{scene}:send_cooldown:{email}"

    @classmethod
    def _send_count_ip_key(cls, client_ip: str, scene: str = PASSWORD_RESET_SCENE) -> str:
        return f"{scene}:send_count_ip:{client_ip}"

    @classmethod
    def _send_cooldown_ip_key(cls, client_ip: str, scene: str = PASSWORD_RESET_SCENE) -> str:
        return f"{scene}:send_cooldown_ip:{client_ip}"

    @classmethod
    def _send_pending_key(cls, email: str, scene: str = PASSWORD_RESET_SCENE) -> str:
        return f"{scene}:send_pending:{email}"

    @classmethod
    def _send_pending_ip_key(cls, client_ip: str, scene: str = PASSWORD_RESET_SCENE) -> str:
        return f"{scene}:send_pending_ip:{client_ip}"

    @classmethod
    def _verify_attempt_key(cls, email: str, scene: str = PASSWORD_RESET_SCENE) -> str:
        return f"{scene}:verify_attempt:{email}"

    @classmethod
    def _verify_lock_key(cls, email: str, scene: str = PASSWORD_RESET_SCENE) -> str:
        return f"{scene}:verify_lock:{email}"

    @classmethod
    def _get_scene_mail_config(cls, scene: str) -> tuple[str, str, str]:
        """根据业务场景返回邮件标题、动作文案和安全提示。"""
        if scene == cls.CHANGE_EMAIL_SCENE:
            return (
                "【OpenAgent】邮箱换绑验证码",
                "邮箱换绑",
                "如果这不是您本人的操作，请忽略此邮件，原邮箱仍然可以正常使用。",
            )

        if scene == cls.LOGIN_CHALLENGE_SCENE:
            return (
                "【OpenAgent】异常登录验证验证码",
                "异常登录验证",
                "如果这不是您本人的操作，请立即修改密码，并在设置中心下线其他登录设备。",
            )

        if scene == cls.REGISTER_SCENE:
            return (
                "【OpenAgent】注册验证码",
                "注册",
                "如果这不是您本人的操作，请忽略此邮件，系统不会在未完成验证码校验前创建账号。",
            )

        return (
            "【OpenAgent】密码重置验证码",
            "密码重置",
            "如果这不是您本人的操作，请忽略此邮件，您的账户仍然是安全的。",
        )

    @classmethod
    def _resolve_client_ip(cls) -> str:
        """获取当前请求客户端IP，不存在请求上下文时回退为unknown。"""
        if not has_request_context():
            return "unknown"
        forwarded_for = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if forwarded_for:
            return forwarded_for
        return (request.remote_addr or "").strip() or "unknown"

    @staticmethod
    def generate_verification_code(length: int = 6) -> str:
        """生成随机验证码"""
        return "".join(secrets.choice(string.digits) for _ in range(length))

    @classmethod
    def build_verification_email_content(cls, code: str, scene: str = PASSWORD_RESET_SCENE) -> tuple[str, str, str]:
        """构建验证码邮件标题、纯文本与HTML正文。"""
        subject, action_label, safety_notice = cls._get_scene_mail_config(scene)

        html_body = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{action_label}验证码</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f7fa;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f7fa; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); overflow: hidden;">
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600; letter-spacing: -0.5px;">
                                🔐 {action_label}验证
                            </h1>
                            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                                OpenAgent AI Agent 平台
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; color: #333333; font-size: 16px; line-height: 1.6;">
                                您好！
                            </p>
                            <p style="margin: 0 0 30px 0; color: #666666; font-size: 15px; line-height: 1.6;">
                                您正在进行{action_label}操作，请使用以下验证码完成验证：
                            </p>
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 30px 0;">
                                <tr>
                                    <td align="center" style="background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%); border: 2px dashed #667eea; border-radius: 8px; padding: 30px;">
                                        <div style="font-size: 36px; font-weight: 700; color: #667eea; letter-spacing: 8px; font-family: 'Courier New', monospace;">
                                            {code}
                                        </div>
                                    </td>
                                </tr>
                            </table>
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 30px 0;">
                                <tr>
                                    <td style="background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px; padding: 15px 20px;">
                                        <p style="margin: 0; color: #856404; font-size: 14px; line-height: 1.6;">
                                            ⏰ <strong>验证码有效期为 5 分钟</strong>，请尽快完成验证。
                                        </p>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0 0 10px 0; color: #999999; font-size: 13px; line-height: 1.6;">
                                {safety_notice}
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e9ecef;">
                            <p style="margin: 0 0 15px 0; color: #666666; font-size: 14px; font-weight: 600;">
                                OpenAgent - 端到端 LLMOps 平台
                            </p>
                            <p style="margin: 0 0 20px 0; color: #999999; font-size: 13px; line-height: 1.6;">
                                多模型 AI Agent 开发与管理平台
                            </p>
                            <table cellpadding="0" cellspacing="0" align="center">
                                <tr>
                                    <td style="padding: 0 10px;">
                                        <a href="http://www.openllm.cloud" style="display: inline-block; color: #667eea; text-decoration: none; font-size: 13px; font-weight: 500;">
                                            🌐 访问官网
                                        </a>
                                    </td>
                                    <td style="padding: 0 10px; color: #dee2e6;">|</td>
                                    <td style="padding: 0 10px;">
                                        <a href="https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents" style="display: inline-block; color: #667eea; text-decoration: none; font-size: 13px; font-weight: 500;">
                                            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style="vertical-align: middle; margin-right: 4px;">
                                                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
                                            </svg>
                                            GitHub
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 20px 0 0 0; color: #adb5bd; font-size: 12px;">
                                © 2026 OpenAgent. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
                <p style="margin: 20px 0 0 0; color: #adb5bd; font-size: 12px; text-align: center;">
                    这是一封自动发送的邮件，请勿直接回复
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
        """

        text_body = f"""
您好！

您正在进行{action_label}操作，验证码为：

{code}

验证码有效期为5分钟，请尽快完成验证。

{safety_notice}

---
OpenAgent AI Agent 平台
官网：http://www.openllm.cloud
GitHub：https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents
        """.strip()

        return subject, text_body, html_body

    def send_verification_code(self, email: str, scene: str = PASSWORD_RESET_SCENE) -> str:
        """发送验证码到指定邮箱"""
        # 1.发送频率限制（邮箱+IP 双维度冷却与窗口计数）
        client_ip = self._resolve_client_ip()
        send_cooldown_key = self._send_cooldown_key(email, scene)
        if redis_client.exists(send_cooldown_key):
            cooldown_seconds = int(redis_client.ttl(send_cooldown_key))
            cooldown_seconds = cooldown_seconds if cooldown_seconds > 0 else self.SEND_COOLDOWN_SECONDS
            raise FailException(f"请求过于频繁，请{cooldown_seconds}秒后再试")

        send_pending_key = self._send_pending_key(email, scene)
        if redis_client.exists(send_pending_key):
            pending_seconds = int(redis_client.ttl(send_pending_key))
            pending_seconds = pending_seconds if pending_seconds > 0 else self.SEND_PENDING_SECONDS
            raise FailException(f"验证码发送中，请{pending_seconds}秒后再试")

        send_cooldown_ip_key = self._send_cooldown_ip_key(client_ip, scene)
        if redis_client.exists(send_cooldown_ip_key):
            cooldown_seconds = int(redis_client.ttl(send_cooldown_ip_key))
            cooldown_seconds = cooldown_seconds if cooldown_seconds > 0 else self.SEND_COOLDOWN_SECONDS
            raise FailException(f"请求过于频繁，请{cooldown_seconds}秒后再试")

        send_pending_ip_key = self._send_pending_ip_key(client_ip, scene)
        if redis_client.exists(send_pending_ip_key):
            pending_seconds = int(redis_client.ttl(send_pending_ip_key))
            pending_seconds = pending_seconds if pending_seconds > 0 else self.SEND_PENDING_SECONDS
            raise FailException(f"验证码发送中，请{pending_seconds}秒后再试")

        send_count_key = self._send_count_key(email, scene)
        send_count = int(redis_client.incr(send_count_key))
        if send_count == 1:
            redis_client.expire(send_count_key, self.SEND_WINDOW_SECONDS)
        if send_count > self.MAX_SEND_COUNT_PER_WINDOW:
            raise FailException("发送验证码次数过多，请稍后再试")

        send_count_ip_key = self._send_count_ip_key(client_ip, scene)
        send_count_ip = int(redis_client.incr(send_count_ip_key))
        if send_count_ip == 1:
            redis_client.expire(send_count_ip_key, self.SEND_WINDOW_SECONDS)
        if send_count_ip > self.MAX_SEND_COUNT_PER_IP_PER_WINDOW:
            raise FailException("发送验证码次数过多，请稍后再试")

        redis_client.setex(send_pending_key, timedelta(seconds=self.SEND_PENDING_SECONDS), "1")
        redis_client.setex(send_pending_ip_key, timedelta(seconds=self.SEND_PENDING_SECONDS), "1")

        # 2.投递邮件发送任务
        try:
            send_verification_email_task.apply_async(
                kwargs={
                    "email": email,
                    "scene": scene,
                    "client_ip": client_ip,
                },
            )
            return ""
        except Exception as e:
            current_app.logger.error(f"投递验证码邮件任务失败: {str(e)}")
            redis_client.delete(send_pending_key)
            redis_client.delete(send_pending_ip_key)
            raise FailException("邮件发送失败,请稍后重试")

    def send_change_email_code(self, email: str) -> str:
        """发送换绑邮箱验证码。"""
        return self.send_verification_code(email, scene=self.CHANGE_EMAIL_SCENE)

    def send_login_challenge_code(self, email: str) -> str:
        """发送异常登录二次验证验证码。"""
        return self.send_verification_code(email, scene=self.LOGIN_CHALLENGE_SCENE)

    def send_register_code(self, email: str) -> str:
        """发送注册验证码。"""
        return self.send_verification_code(email, scene=self.REGISTER_SCENE)

    def send_login_alert_email(
        self,
        email: str,
        *,
        account_name: str,
        client_ip: str,
        user_agent: str,
        login_at,
    ) -> None:
        """发送新 IP 登录提醒邮件。"""
        login_time = login_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        subject = "【OpenAgent】检测到新 IP 登录"
        text_body = f"""
您好，{account_name}：

系统检测到您的账号刚刚发生了一次新的 IP 登录：

登录时间：{login_time}
登录 IP：{client_ip or "unknown"}
设备信息：{user_agent or "unknown"}

如果这是您本人的操作，则无需处理。
如果这不是您本人的操作，请尽快修改密码，并在设置中心下线其他登录设备。

OpenAgent AI Agent 平台
        """.strip()
        html_body = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>新 IP 登录提醒</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; background-color: #f5f7fa;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f7fa; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; overflow: hidden;">
                    <tr>
                        <td style="background: linear-gradient(135deg, #e85d04 0%, #dc2f02 100%); padding: 32px 28px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">登录安全提醒</h1>
                            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">检测到新的 IP 登录</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 32px 28px; color: #333333; font-size: 15px; line-height: 1.8;">
                            <p style="margin: 0 0 18px 0;">您好，{account_name}：</p>
                            <p style="margin: 0 0 18px 0;">系统检测到您的账号刚刚发生了一次新的 IP 登录：</p>
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #fff7ed; border: 1px solid #fed7aa; border-radius: 8px; margin-bottom: 20px;">
                                <tr>
                                    <td style="padding: 18px 20px;">
                                        <div><strong>登录时间：</strong>{login_time}</div>
                                        <div><strong>登录 IP：</strong>{client_ip or "unknown"}</div>
                                        <div><strong>设备信息：</strong>{user_agent or "unknown"}</div>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0 0 12px 0;">如果这是您本人的操作，则无需处理。</p>
                            <p style="margin: 0;">如果这不是您本人的操作，请尽快修改密码，并在设置中心下线其他登录设备。</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """.strip()

        msg = Message(
            subject=subject,
            recipients=[email],
            body=text_body,
            html=html_body,
        )

        try:
            self.mail.send(msg)
        except Exception as e:
            current_app.logger.error(f"发送登录安全提醒邮件失败: {str(e)}")
            raise FailException("邮件发送失败,请稍后重试")

    def verify_code(self, email: str, code: str, scene: str = PASSWORD_RESET_SCENE) -> bool:
        """验证验证码是否正确"""
        code_key = self._code_key(email, scene)
        verify_attempt_key = self._verify_attempt_key(email, scene)
        verify_lock_key = self._verify_lock_key(email, scene)

        if redis_client.exists(verify_lock_key):
            raise FailException("验证码错误次数过多，请15分钟后再试")

        stored_code = redis_client.get(code_key)

        if not stored_code:
            return False

        if secrets.compare_digest(stored_code.decode(), code):
            redis_client.delete(code_key)
            redis_client.delete(verify_attempt_key)
            redis_client.delete(verify_lock_key)
            return True

        verify_attempt = int(redis_client.incr(verify_attempt_key))
        if verify_attempt == 1:
            code_ttl = int(redis_client.ttl(code_key))
            attempt_ttl = code_ttl if code_ttl > 0 else self.CODE_TTL_SECONDS
            redis_client.expire(verify_attempt_key, attempt_ttl)

        if verify_attempt >= self.MAX_VERIFY_ATTEMPTS:
            redis_client.setex(verify_lock_key, timedelta(seconds=self.VERIFY_LOCK_SECONDS), "1")
            redis_client.delete(code_key)
            redis_client.delete(verify_attempt_key)
            raise FailException("验证码错误次数过多，请15分钟后再试")

        return False

    def verify_change_email_code(self, email: str, code: str) -> bool:
        """验证换绑邮箱验证码。"""
        return self.verify_code(email, code, scene=self.CHANGE_EMAIL_SCENE)

    def verify_login_challenge_code(self, email: str, code: str) -> bool:
        """验证异常登录二次验证码。"""
        return self.verify_code(email, code, scene=self.LOGIN_CHALLENGE_SCENE)

    def verify_register_code(self, email: str, code: str) -> bool:
        """验证注册验证码。"""
        return self.verify_code(email, code, scene=self.REGISTER_SCENE)
