import base64
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from flask import request
from injector import inject

from internal.exception import FailException
from internal.extension.redis_extension import redis_client
from internal.model import Account, AccountOAuth
from pkg.password import compare_password, hash_password
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .email_service import EmailService
from .jwt_service import JwtService


@inject
@dataclass
class AccountService(BaseService):
    """账号服务"""
    db: SQLAlchemy
    jwt_service: JwtService
    email_service: EmailService
    LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60
    LOGIN_LOCK_SECONDS = 15 * 60
    MAX_LOGIN_FAILURE_PER_EMAIL = 5
    MAX_LOGIN_FAILURE_PER_IP = 20

    @classmethod
    def _login_email_fail_key(cls, email: str) -> str:
        return f"auth:login_fail:email:{email}"

    @classmethod
    def _login_ip_fail_key(cls, client_ip: str) -> str:
        return f"auth:login_fail:ip:{client_ip}"

    @classmethod
    def _login_email_lock_key(cls, email: str) -> str:
        return f"auth:login_lock:email:{email}"

    @classmethod
    def _login_ip_lock_key(cls, client_ip: str) -> str:
        return f"auth:login_lock:ip:{client_ip}"

    def _is_login_locked(self, email: str, client_ip: str) -> bool:
        try:
            return bool(
                redis_client.exists(self._login_email_lock_key(email))
                or redis_client.exists(self._login_ip_lock_key(client_ip))
            )
        except Exception as e:
            logging.warning("读取登录锁状态失败，跳过登录锁校验: %s", e)
            return False

    def _record_login_failure(self, email: str, client_ip: str) -> bool:
        """记录登录失败次数并在达到阈值时加锁，返回是否已触发锁定。"""
        lock_triggered = False
        try:
            email_fail_key = self._login_email_fail_key(email)
            email_fail_count = int(redis_client.incr(email_fail_key))
            if email_fail_count == 1:
                redis_client.expire(email_fail_key, self.LOGIN_FAILURE_WINDOW_SECONDS)
            if email_fail_count >= self.MAX_LOGIN_FAILURE_PER_EMAIL:
                redis_client.setex(
                    self._login_email_lock_key(email),
                    timedelta(seconds=self.LOGIN_LOCK_SECONDS),
                    "1",
                )
                lock_triggered = True

            ip_fail_key = self._login_ip_fail_key(client_ip)
            ip_fail_count = int(redis_client.incr(ip_fail_key))
            if ip_fail_count == 1:
                redis_client.expire(ip_fail_key, self.LOGIN_FAILURE_WINDOW_SECONDS)
            if ip_fail_count >= self.MAX_LOGIN_FAILURE_PER_IP:
                redis_client.setex(
                    self._login_ip_lock_key(client_ip),
                    timedelta(seconds=self.LOGIN_LOCK_SECONDS),
                    "1",
                )
                lock_triggered = True
        except Exception as e:
            logging.warning("记录登录失败次数失败，跳过防暴力破解计数: %s", e)
        return lock_triggered

    def _clear_login_failure(self, email: str, client_ip: str) -> None:
        try:
            redis_client.delete(
                self._login_email_fail_key(email),
                self._login_ip_fail_key(client_ip),
                self._login_email_lock_key(email),
                self._login_ip_lock_key(client_ip),
            )
        except Exception as e:
            logging.warning("清理登录失败计数失败: %s", e)

    def get_account(self, account_id: UUID) -> Account:
        """根据id获取指定的账号模型"""
        return self.get(Account, account_id)

    def get_account_oauth_by_provider_name_and_openid(
            self,
            provider_name: str,
            openid: str,
    ) -> AccountOAuth:
        """根据传递的提供者名字+openid获取第三方授权认证记录"""
        return self.db.session.query(AccountOAuth).filter(
            AccountOAuth.provider == provider_name,
            AccountOAuth.openid == openid,
        ).one_or_none()

    def get_account_by_email(self, email: str) -> Account:
        """根据传递的邮箱查询账号信息"""
        return self.db.session.query(Account).filter(
            Account.email == email,
        ).one_or_none()

    def create_account(self, **kwargs) -> Account:
        """根据传递的键值对创建账号信息"""
        return self.create(Account, **kwargs)

    def update_password(self, password: str, account: Account) -> Account:
        """更新当前账号密码信息"""
        # 1.生成密码随机盐值
        salt = secrets.token_bytes(16)
        base64_salt = base64.b64encode(salt).decode()

        # 2.利用盐值和password进行加密
        password_hashed = hash_password(password, salt)
        base64_password_hashed = base64.b64encode(password_hashed).decode()

        # 3.更新账号信息
        self.update_account(account, password=base64_password_hashed, password_salt=base64_salt)

        return account

    def update_account(self, account: Account, **kwargs) -> Account:
        """根据传递的信息更新账号"""
        self.update(account, **kwargs)
        return account

    def password_login(self, email: str, password: str) -> dict[str, Any]:
        """根据传递的密码 + 邮箱登录特定的账号"""
        normalized_email = (email or "").strip().lower()
        client_ip = (request.remote_addr or "").strip() or "unknown"

        # 0.登录前先校验是否触发锁定
        if self._is_login_locked(normalized_email, client_ip):
            raise FailException("登录失败次数过多，请15分钟后再试")

        # 1.根据传递的邮箱查询账号是否存在
        account = self.get_account_by_email(normalized_email)
        if not account or not account.is_password_set:
            if self._record_login_failure(normalized_email, client_ip):
                raise FailException("登录失败次数过多，请15分钟后再试")
            raise FailException("账号不存在或者密码错误")

        # 2.校验账号密码是否正确
        if not compare_password(
            password,
            account.password,
            account.password_salt
        ):
            if self._record_login_failure(normalized_email, client_ip):
                raise FailException("登录失败次数过多，请15分钟后再试")
            raise FailException("账号不存在或者密码错误")

        # 2.5 登录成功后清理失败计数
        self._clear_login_failure(normalized_email, client_ip)

        # 3.生成授权凭证信息
        expire_at = int((datetime.now() + timedelta(days=30)).timestamp())
        payload = {
            "sub": str(account.id),
            "iss": "llmops",
            "exp": expire_at,
        }
        access_token = self.jwt_service.generate_token(payload)

        # 4.更新账号信息，涵盖最后一次登录时间，以及ip地址
        self.update(
            account,
            last_login_at=datetime.now(UTC),
            last_login_ip=client_ip,
        )

        return {
            "expire_at": expire_at,
            "access_token": access_token,
        }

    def send_reset_code(self, email: str) -> None:
        """发送密码重置验证码"""
        # 1.检查账号是否存在
        account = self.get_account_by_email(email)
        if not account:
            return

        # 2.发送验证码
        self.email_service.send_verification_code(email)

    def reset_password(self, email: str, code: str, new_password: str) -> None:
        """重置密码"""
        # 1.验证验证码
        if not self.email_service.verify_code(email, code):
            raise FailException("验证码错误或已过期")

        # 2.获取账号
        account = self.get_account_by_email(email)
        if not account:
            raise FailException("账号不存在")

        # 3.更新密码
        self.update_password(new_password, account)

