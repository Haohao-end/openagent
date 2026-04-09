import base64
import ipaddress
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from flask import has_request_context, request
from injector import inject
import requests
from sqlalchemy.exc import SQLAlchemyError

from internal.exception import FailException, NotFoundException, UnauthorizedException
from internal.extension.redis_extension import redis_client
from internal.model import Account, AccountOAuth, AccountSession
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
    SUPPORTED_OAUTH_PROVIDERS = ("github", "google")
    LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60
    LOGIN_LOCK_SECONDS = 15 * 60
    MAX_LOGIN_FAILURE_PER_EMAIL = 5
    MAX_LOGIN_FAILURE_PER_IP = 20
    SESSION_EXPIRE_DAYS = 30
    SESSION_TOUCH_INTERVAL_SECONDS = 5 * 60
    LOGIN_HISTORY_LIMIT = 20
    LOGIN_CHALLENGE_TTL_SECONDS = 10 * 60
    IP_LOCATION_CACHE_TTL_SECONDS = 24 * 60 * 60
    IP_LOCATION_LOOKUP_TIMEOUT_SECONDS = 3

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

    @classmethod
    def _login_challenge_key(cls, challenge_id: str) -> str:
        return f"auth:login_challenge:{challenge_id}"

    @classmethod
    def _ip_location_cache_key(cls, client_ip: str) -> str:
        return f"account:ip_location:{client_ip}"

    @classmethod
    def _normalize_email(cls, email: str) -> str:
        return (email or "").strip().lower()

    @classmethod
    def _now(cls) -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    @classmethod
    def _normalize_ip(cls, client_ip: str) -> str:
        normalized_ip = (client_ip or "").strip()
        if not normalized_ip or normalized_ip.lower() == "unknown":
            return ""
        return normalized_ip

    @classmethod
    def _mask_email(cls, email: str) -> str:
        normalized_email = (email or "").strip()
        if "@" not in normalized_email:
            return normalized_email

        local_part, domain = normalized_email.split("@", 1)
        if len(local_part) <= 1:
            masked_local_part = "*"
        elif len(local_part) == 2:
            masked_local_part = f"{local_part[0]}*"
        else:
            masked_local_part = f"{local_part[:2]}{'*' * max(len(local_part) - 2, 1)}"

        return f"{masked_local_part}@{domain}"

    @classmethod
    def _resolve_client_ip(cls) -> str:
        if not has_request_context():
            return "unknown"

        forwarded_for = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if forwarded_for:
            return forwarded_for

        return (request.remote_addr or "").strip() or "unknown"

    @classmethod
    def _resolve_user_agent(cls) -> str:
        if not has_request_context():
            return "unknown"
        return (request.headers.get("User-Agent") or "").strip() or "unknown"

    @classmethod
    def _resolve_local_ip_location(cls, client_ip: str) -> str:
        try:
            ip = ipaddress.ip_address(client_ip)
        except ValueError:
            return ""

        if ip.is_loopback:
            return "本机"
        if ip.is_private or ip.is_link_local:
            return "局域网"
        if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return "特殊地址"
        return ""

    @classmethod
    def _normalize_location_name(cls, location: str) -> str:
        return str(location or "").strip()

    @classmethod
    def _deduplicate_location_parts(cls, parts: list[str]) -> list[str]:
        deduplicated_parts: list[str] = []
        for part in parts:
            normalized_part = cls._normalize_location_name(part)
            if not normalized_part or normalized_part in deduplicated_parts:
                continue
            deduplicated_parts.append(normalized_part)
        return deduplicated_parts

    @classmethod
    def _is_domestic_location(cls, country: str, *parts: str) -> bool:
        normalized_country = cls._normalize_location_name(country)
        if normalized_country.startswith("中国") or normalized_country in ("香港", "澳门", "台湾"):
            return True

        china_suffixes = (
            "省",
            "市",
            "自治区",
            "特别行政区",
            "自治州",
            "地区",
            "盟",
            "区",
            "县",
        )
        return any(
            cls._normalize_location_name(part).endswith(china_suffixes)
            for part in parts
        )

    def _format_ip_location(self, payload: dict[str, Any]) -> str:
        country = self._normalize_location_name(payload.get("country", ""))
        region = self._normalize_location_name(payload.get("regionName", ""))
        city = self._normalize_location_name(payload.get("city", ""))
        district = self._normalize_location_name(
            payload.get("district")
            or payload.get("districtName")
            or payload.get("district_name")
            or "",
        )

        detail_parts = self._deduplicate_location_parts([region, city, district])
        if self._is_domestic_location(country, region, city, district):
            if detail_parts:
                return "".join(detail_parts)
            return country

        full_parts = self._deduplicate_location_parts([country, region, city, district])
        return " · ".join(full_parts)

    def _get_cached_ip_location(self, client_ip: str, cache_map: dict[str, str]) -> str:
        normalized_ip = self._normalize_ip(client_ip)
        if not normalized_ip:
            return ""

        if normalized_ip not in cache_map:
            cache_map[normalized_ip] = self.resolve_ip_location(normalized_ip)
        return cache_map[normalized_ip]

    @classmethod
    def _describe_device(cls, user_agent: str) -> str:
        normalized = (user_agent or "").lower()
        if not normalized or normalized == "unknown":
            return "未知设备"

        platform = "设备"
        browser = "浏览器"

        if "iphone" in normalized:
            platform = "iPhone"
        elif "ipad" in normalized:
            platform = "iPad"
        elif "android" in normalized:
            platform = "Android"
        elif "macintosh" in normalized or "mac os" in normalized:
            platform = "macOS"
        elif "windows" in normalized:
            platform = "Windows"
        elif "linux" in normalized:
            platform = "Linux"

        if "edg/" in normalized:
            browser = "Edge"
        elif "chrome/" in normalized and "edg/" not in normalized:
            browser = "Chrome"
        elif "firefox/" in normalized:
            browser = "Firefox"
        elif "safari/" in normalized and "chrome/" not in normalized:
            browser = "Safari"

        return f"{platform} · {browser}"

    def resolve_ip_location(self, client_ip: str) -> str:
        normalized_ip = self._normalize_ip(client_ip)
        if not normalized_ip:
            return ""

        local_location = self._resolve_local_ip_location(normalized_ip)
        if local_location:
            return local_location

        cache_key = self._ip_location_cache_key(normalized_ip)
        try:
            cached_value = redis_client.get(cache_key)
            if cached_value is not None:
                return cached_value.decode() if isinstance(cached_value, bytes) else str(cached_value)
        except Exception as e:
            logging.warning("读取 IP 地点缓存失败，已跳过: %s", e)

        location = ""
        try:
            response = requests.get(
                f"http://ip-api.com/json/{normalized_ip}?lang=zh-CN",
                timeout=self.IP_LOCATION_LOOKUP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and payload.get("status") == "success":
                location = self._format_ip_location(payload)
        except Exception as e:
            logging.warning("查询 IP 地点失败，已跳过: %s", e)

        try:
            redis_client.setex(
                cache_key,
                timedelta(seconds=self.IP_LOCATION_CACHE_TTL_SECONDS),
                location,
            )
        except Exception as e:
            logging.warning("写入 IP 地点缓存失败，已跳过: %s", e)

        return location

    def _resolve_session_status(self, account_session: AccountSession, now: datetime | None = None) -> str:
        now = now or self._now()
        if account_session.revoked_at is not None:
            return "revoked"
        if account_session.expires_at and account_session.expires_at < now:
            return "expired"
        return "active"

    @classmethod
    def _log_session_storage_warning(cls, action: str, error: Exception) -> None:
        logging.warning("账号会话存储%s失败，已回退兼容模式: %s", action, error)

    @classmethod
    def _build_legacy_session_id(cls, account_id: UUID | str) -> UUID:
        return uuid5(NAMESPACE_DNS, f"legacy-current-session:{account_id}")

    def _build_legacy_current_session(self, account: Account) -> dict[str, Any]:
        fallback_time = getattr(account, "last_login_at", None) or getattr(account, "created_at", None) or self._now()
        user_agent = self._resolve_user_agent()
        legacy_ip = getattr(account, "last_login_ip", "") or self._resolve_client_ip()

        return {
            "id": self._build_legacy_session_id(account.id),
            "current": True,
            "legacy": True,
            "device_name": self._describe_device(user_agent),
            "user_agent": user_agent,
            "ip": legacy_ip,
            "location": self.resolve_ip_location(legacy_ip),
            "created_at": fallback_time,
            "last_active_at": fallback_time,
            "expires_at": None,
        }

    def _build_legacy_login_history_item(self, account: Account) -> dict[str, Any]:
        fallback_time = getattr(account, "last_login_at", None) or getattr(account, "created_at", None) or self._now()
        user_agent = self._resolve_user_agent()
        legacy_ip = getattr(account, "last_login_ip", "") or self._resolve_client_ip()

        return {
            "id": self._build_legacy_session_id(account.id),
            "current": True,
            "legacy": True,
            "device_name": self._describe_device(user_agent),
            "user_agent": user_agent,
            "ip": legacy_ip,
            "location": self.resolve_ip_location(legacy_ip),
            "status": "legacy",
            "unusual_ip": self._is_unusual_login_ip(account, legacy_ip),
            "created_at": fallback_time,
            "last_active_at": fallback_time,
            "expires_at": None,
            "revoked_at": None,
        }

    def _is_unusual_login_ip(
        self,
        account: Account,
        client_ip: str,
        *,
        current_session_id: UUID | str | None = None,
    ) -> bool:
        normalized_ip = self._normalize_ip(client_ip)
        if not normalized_ip:
            return False

        prior_session_count = 0
        for account_session in self._list_account_sessions_for_read(account.id):
            if current_session_id and str(account_session.id) == str(current_session_id):
                continue

            prior_session_count += 1
            if self._normalize_ip(account_session.last_login_ip) == normalized_ip:
                return False

        return prior_session_count > 0

    def _list_account_sessions_for_read(self, account_id: UUID) -> list[AccountSession]:
        """读取账号会话列表；当会话表未就绪时回退为空列表。"""
        try:
            return list(self.get_account_sessions_by_account_id(account_id))
        except SQLAlchemyError as e:
            self._log_session_storage_warning("读取列表", e)
            return []

    def _should_require_login_challenge(self, account: Account, client_ip: str) -> bool:
        """根据登录风险决定是否需要额外邮箱验证码验证。"""
        normalized_ip = self._normalize_ip(client_ip)
        if not normalized_ip:
            return False

        if not getattr(account, "last_login_at", None):
            return False

        last_login_ip = self._normalize_ip(getattr(account, "last_login_ip", ""))
        if last_login_ip and last_login_ip == normalized_ip:
            return False

        if self._is_unusual_login_ip(account, normalized_ip):
            return True

        return bool(last_login_ip and last_login_ip != normalized_ip)

    def _build_login_challenge_response(self, challenge_id: str, email: str, risk_reason: str) -> dict[str, Any]:
        return {
            "challenge_required": True,
            "challenge_id": challenge_id,
            "challenge_type": "email_code",
            "masked_email": self._mask_email(email),
            "risk_reason": risk_reason,
        }

    def _load_login_challenge(self, challenge_id: str) -> dict[str, Any]:
        raw_payload = redis_client.get(self._login_challenge_key(challenge_id))
        if not raw_payload:
            raise FailException("登录验证已过期，请重新登录")

        try:
            payload = json.loads(raw_payload.decode() if isinstance(raw_payload, bytes) else raw_payload)
        except (TypeError, ValueError):
            redis_client.delete(self._login_challenge_key(challenge_id))
            raise FailException("登录验证已失效，请重新登录")

        if not isinstance(payload, dict) or not payload.get("account_id") or not payload.get("email"):
            redis_client.delete(self._login_challenge_key(challenge_id))
            raise FailException("登录验证已失效，请重新登录")

        return payload

    def _create_login_challenge(self, account: Account, *, risk_reason: str = "new_ip") -> dict[str, Any]:
        challenge_id = str(uuid4())
        challenge_key = self._login_challenge_key(challenge_id)
        payload = {
            "account_id": str(account.id),
            "email": self._normalize_email(account.email),
            "risk_reason": risk_reason,
            "created_at": int(self._now().replace(tzinfo=UTC).timestamp()),
        }

        redis_client.setex(
            challenge_key,
            timedelta(seconds=self.LOGIN_CHALLENGE_TTL_SECONDS),
            json.dumps(payload),
        )

        try:
            self.email_service.send_login_challenge_code(payload["email"])
        except Exception:
            redis_client.delete(challenge_key)
            raise

        return self._build_login_challenge_response(challenge_id, payload["email"], risk_reason)

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

    def get_account_oauth_by_account_id_and_provider_name(
            self,
            account_id: UUID,
            provider_name: str,
    ) -> AccountOAuth:
        """根据账号id与 provider 获取绑定记录"""
        return self.db.session.query(AccountOAuth).filter(
            AccountOAuth.account_id == account_id,
            AccountOAuth.provider == provider_name,
        ).one_or_none()

    def get_account_oauths_by_account_id(self, account_id: UUID) -> list[AccountOAuth]:
        """根据账号 id 获取全部第三方绑定"""
        return self.db.session.query(AccountOAuth).filter(
            AccountOAuth.account_id == account_id,
        ).all()

    def get_account_by_email(self, email: str) -> Account:
        """根据传递的邮箱查询账号信息"""
        normalized_email = self._normalize_email(email)
        return self.db.session.query(Account).filter(
            Account.email == normalized_email,
        ).one_or_none()

    def get_account_session(self, session_id: UUID | str) -> AccountSession | None:
        """根据会话 id 获取账号会话。"""
        return self.get(AccountSession, session_id)

    def get_account_sessions_by_account_id(self, account_id: UUID) -> list[AccountSession]:
        """获取账号下的全部会话记录。"""
        return self.db.session.query(AccountSession).filter(
            AccountSession.account_id == account_id,
        ).order_by(
            AccountSession.last_active_at.desc(),
            AccountSession.created_at.desc(),
        ).all()

    def create_account(self, **kwargs) -> Account:
        """根据传递的键值对创建账号信息"""
        if "email" in kwargs:
            kwargs["email"] = self._normalize_email(kwargs["email"])
        return self.create(Account, **kwargs)

    def create_account_session(self, account: Account) -> AccountSession:
        """创建新的账号登录会话。"""
        now = self._now()
        return self.create(
            AccountSession,
            id=uuid4(),
            account_id=account.id,
            user_agent=self._resolve_user_agent(),
            last_login_ip=self._resolve_client_ip(),
            last_active_at=now,
            expires_at=now + timedelta(days=self.SESSION_EXPIRE_DAYS),
        )

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

    def change_password(self, account: Account, current_password: str, new_password: str) -> Account:
        """校验当前密码后更新密码；首次设置密码时允许不传当前密码。"""
        current_password = (current_password or "").strip()
        new_password = (new_password or "").strip()

        if account.is_password_set:
            if not current_password:
                raise FailException("请输入当前密码")
            if not compare_password(
                current_password,
                account.password,
                account.password_salt,
            ):
                raise FailException("当前密码错误")

        if not new_password:
            raise FailException("新密码不能为空")

        if account.is_password_set and current_password == new_password:
            raise FailException("新密码不能与当前密码相同")

        return self.update_password(new_password, account)

    def issue_credential(
        self,
        account: Account,
        *,
        session: AccountSession | None = None,
        update_login_metadata: bool = True,
        skip_login_alert: bool = False,
    ) -> dict[str, Any]:
        """为当前账号签发带会话标识的 JWT。"""
        now = self._now()
        expire_at_dt = now + timedelta(days=self.SESSION_EXPIRE_DAYS)
        client_ip = self._resolve_client_ip()
        user_agent = self._resolve_user_agent()
        is_new_session = session is None

        if session is None:
            try:
                session = self.create_account_session(account)
            except SQLAlchemyError as e:
                self._log_session_storage_warning("创建", e)
                session = None

        if session is not None:
            try:
                self.update(
                    session,
                    user_agent=user_agent,
                    last_login_ip=client_ip,
                    last_active_at=now,
                    expires_at=expire_at_dt,
                    revoked_at=None,
                )
            except SQLAlchemyError as e:
                self._log_session_storage_warning("刷新", e)
                session = None

        expire_at = int(expire_at_dt.replace(tzinfo=UTC).timestamp())
        payload = {
            "sub": str(account.id),
            "iss": "llmops",
            "exp": expire_at,
        }
        if session is not None:
            payload["jti"] = str(session.id)
        access_token = self.jwt_service.generate_token(payload)

        if update_login_metadata:
            self.update(
                account,
                last_login_at=now,
                last_login_ip=client_ip,
            )

            current_session_id = getattr(session, "id", None)
            if (
                not skip_login_alert
                and is_new_session
                and self._is_unusual_login_ip(
                account,
                client_ip,
                current_session_id=current_session_id,
                )
            ):
                try:
                    self.email_service.send_login_alert_email(
                        account.email,
                        account_name=account.name or account.email,
                        client_ip=client_ip,
                        user_agent=user_agent,
                        login_at=now,
                    )
                except Exception as e:
                    logging.warning("发送异常登录提醒失败，已跳过: %s", e)

        return {
            "expire_at": expire_at,
            "access_token": access_token,
        }

    def validate_access_session(self, payload: dict[str, Any]) -> AccountSession | None:
        """校验当前 JWT 绑定的账号会话，兼容旧 token 无 jti 的情况。"""
        session_id = payload.get("jti")
        account_id = payload.get("sub")
        if not session_id:
            return None

        try:
            account_session = self.get_account_session(session_id)
        except SQLAlchemyError as e:
            self._log_session_storage_warning("校验", e)
            return None

        if not account_session or str(account_session.account_id) != str(account_id):
            raise UnauthorizedException("登录会话不存在或已失效,请重新登录")

        if account_session.revoked_at is not None:
            raise UnauthorizedException("登录会话已失效,请重新登录")

        expires_at = getattr(account_session, "expires_at", None)
        if expires_at and expires_at < self._now():
            raise UnauthorizedException("登录会话已过期,请重新登录")

        self.touch_account_session(account_session)
        return account_session

    def touch_account_session(self, account_session: AccountSession) -> AccountSession:
        """按固定间隔刷新会话活跃时间，避免每次请求都落库。"""
        now = self._now()
        last_active_at = getattr(account_session, "last_active_at", None)
        if (
            last_active_at is not None
            and (now - last_active_at).total_seconds() < self.SESSION_TOUCH_INTERVAL_SECONDS
            and getattr(account_session, "last_login_ip", "") == self._resolve_client_ip()
            and getattr(account_session, "user_agent", "") == self._resolve_user_agent()
        ):
            return account_session

        try:
            self.update(
                account_session,
                last_active_at=now,
                last_login_ip=self._resolve_client_ip(),
                user_agent=self._resolve_user_agent(),
            )
        except SQLAlchemyError as e:
            self._log_session_storage_warning("更新活跃时间", e)
        return account_session

    def get_account_oauth_bindings(self, account: Account) -> list[dict[str, Any]]:
        """返回当前账号固定支持的第三方绑定状态。"""
        binding_map = {
            item.provider: item
            for item in self.get_account_oauths_by_account_id(account.id)
        }

        result = []
        for provider_name in self.SUPPORTED_OAUTH_PROVIDERS:
            binding = binding_map.get(provider_name)
            result.append({
                "provider": provider_name,
                "bound": binding is not None,
                "bound_at": binding.created_at if binding else None,
            })
        return result

    def update_account(self, account: Account, **kwargs) -> Account:
        """根据传递的信息更新账号"""
        self.update(account, **kwargs)
        return account

    def get_account_sessions(
        self,
        account: Account,
        current_session_id: UUID | str | None = None,
    ) -> list[dict[str, Any]]:
        """返回当前账号有效会话列表。"""
        sessions = []
        now = self._now()
        ip_location_cache: dict[str, str] = {}
        for account_session in self._list_account_sessions_for_read(account.id):
            if account_session.revoked_at is not None:
                continue
            if account_session.expires_at and account_session.expires_at < now:
                continue

            sessions.append({
                "id": account_session.id,
                "current": bool(current_session_id) and str(account_session.id) == str(current_session_id),
                "legacy": False,
                "device_name": self._describe_device(account_session.user_agent),
                "user_agent": account_session.user_agent or "unknown",
                "ip": account_session.last_login_ip or "",
                "location": self._get_cached_ip_location(account_session.last_login_ip, ip_location_cache),
                "created_at": account_session.created_at,
                "last_active_at": account_session.last_active_at,
                "expires_at": account_session.expires_at,
            })

        if current_session_id is None:
            sessions.append(self._build_legacy_current_session(account))

        sessions.sort(
            key=lambda item: (
                item.get("current", False),
                item.get("last_active_at") or datetime.min,
                item.get("created_at") or datetime.min,
            ),
            reverse=True,
        )
        return sessions

    def get_account_login_history(
        self,
        account: Account,
        current_session_id: UUID | str | None = None,
        *,
        status: str = "all",
        search: str = "",
        current_page: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        """返回当前账号最近的登录历史，并标记首次出现的新 IP。"""
        page_size = self.LOGIN_HISTORY_LIMIT if page_size is None else page_size
        all_sessions = self._list_account_sessions_for_read(account.id)
        chronological_sessions = sorted(
            all_sessions,
            key=lambda item: (
                item.created_at or datetime.min,
                item.last_active_at or datetime.min,
                str(item.id),
            ),
        )

        seen_ips: set[str] = set()
        prior_session_count = 0
        unusual_ip_map: dict[str, bool] = {}
        for account_session in chronological_sessions:
            normalized_ip = self._normalize_ip(account_session.last_login_ip)
            unusual_ip = bool(prior_session_count > 0 and normalized_ip and normalized_ip not in seen_ips)
            unusual_ip_map[str(account_session.id)] = unusual_ip
            if normalized_ip:
                seen_ips.add(normalized_ip)
            prior_session_count += 1

        now = self._now()
        history = []
        ip_location_cache: dict[str, str] = {}
        recent_sessions = sorted(
            all_sessions,
            key=lambda item: (
                item.created_at or datetime.min,
                item.last_active_at or datetime.min,
                str(item.id),
            ),
            reverse=True,
        )

        for account_session in recent_sessions:
            history.append({
                "id": account_session.id,
                "current": bool(current_session_id) and str(account_session.id) == str(current_session_id),
                "legacy": False,
                "device_name": self._describe_device(account_session.user_agent),
                "user_agent": account_session.user_agent or "unknown",
                "ip": account_session.last_login_ip or "",
                "location": self._get_cached_ip_location(account_session.last_login_ip, ip_location_cache),
                "status": self._resolve_session_status(account_session, now),
                "unusual_ip": unusual_ip_map.get(str(account_session.id), False),
                "created_at": account_session.created_at,
                "last_active_at": account_session.last_active_at,
                "expires_at": account_session.expires_at,
                "revoked_at": account_session.revoked_at,
            })

        if current_session_id is None:
            history.insert(0, self._build_legacy_login_history_item(account))

        normalized_status = (status or "all").strip().lower() or "all"
        normalized_search = (search or "").strip().lower()
        if normalized_status != "all":
            history = [item for item in history if str(item.get("status", "")).lower() == normalized_status]
        if normalized_search:
            history = [
                item for item in history
                if normalized_search in str(item.get("device_name", "")).lower()
                or normalized_search in str(item.get("user_agent", "")).lower()
                or normalized_search in str(item.get("ip", "")).lower()
                or normalized_search in str(item.get("location", "")).lower()
            ]

        total = len(history)
        safe_current_page = max(current_page or 1, 1)
        safe_page_size = max(page_size or self.LOGIN_HISTORY_LIMIT, 1)
        start = (safe_current_page - 1) * safe_page_size
        end = start + safe_page_size

        return {
            "history": history[start:end],
            "total": total,
            "current_page": safe_current_page,
            "page_size": safe_page_size,
        }

    def revoke_account_session(
        self,
        account: Account,
        session_id: UUID | str,
        *,
        current_session_id: UUID | str | None = None,
        allow_current: bool = False,
    ) -> AccountSession:
        """撤销指定账号会话。"""
        account_session = self.get_account_session(session_id)
        if not account_session or str(account_session.account_id) != str(account.id):
            raise NotFoundException("登录会话不存在")

        if (
            not allow_current
            and current_session_id is not None
            and str(account_session.id) == str(current_session_id)
        ):
            raise FailException("当前设备请使用退出登录操作")

        if account_session.revoked_at is None:
            self.update(account_session, revoked_at=self._now())

        return account_session

    def revoke_other_account_sessions(
        self,
        account: Account,
        current_session_id: UUID | str | None,
    ) -> int:
        """撤销当前账号除当前设备外的所有有效会话。"""
        if not current_session_id:
            raise FailException("当前登录凭证较旧，请重新登录后再管理设备")

        revoked_count = 0
        for account_session in self.get_account_sessions_by_account_id(account.id):
            if str(account_session.id) == str(current_session_id):
                continue
            if account_session.revoked_at is not None:
                continue
            if account_session.expires_at and account_session.expires_at < self._now():
                continue
            self.update(account_session, revoked_at=self._now())
            revoked_count += 1

        return revoked_count

    def send_change_email_code(self, account: Account, email: str) -> None:
        """向新邮箱发送换绑验证码。"""
        normalized_email = self._normalize_email(email)
        if normalized_email == self._normalize_email(account.email):
            raise FailException("新邮箱不能与当前邮箱相同")

        existing_account = self.get_account_by_email(normalized_email)
        if existing_account and str(existing_account.id) != str(account.id):
            raise FailException("该邮箱已被其他账号使用")

        self.email_service.send_change_email_code(normalized_email)

    def update_email(
        self,
        account: Account,
        email: str,
        code: str,
        current_password: str = "",
    ) -> Account:
        """校验验证码后更新当前账号邮箱。"""
        normalized_email = self._normalize_email(email)
        if normalized_email == self._normalize_email(account.email):
            raise FailException("新邮箱不能与当前邮箱相同")

        existing_account = self.get_account_by_email(normalized_email)
        if existing_account and str(existing_account.id) != str(account.id):
            raise FailException("该邮箱已被其他账号使用")

        if account.is_password_set:
            current_password = (current_password or "").strip()
            if not current_password:
                raise FailException("换绑邮箱前请输入当前密码")
            if not compare_password(
                current_password,
                account.password,
                account.password_salt,
            ):
                raise FailException("当前密码错误")

        if not self.email_service.verify_change_email_code(normalized_email, code):
            raise FailException("验证码错误或已过期")

        return self.update_account(account, email=normalized_email)

    def begin_login(self, account: Account) -> dict[str, Any]:
        """根据登录风险返回授权凭证或二次验证挑战。"""
        client_ip = self._resolve_client_ip()
        if self._should_require_login_challenge(account, client_ip):
            return self._create_login_challenge(account, risk_reason="new_ip")
        return self.issue_credential(account)

    def resend_login_challenge(self, challenge_id: str) -> dict[str, Any]:
        """重发登录二次验证验证码。"""
        payload = self._load_login_challenge(challenge_id)
        self.email_service.send_login_challenge_code(payload["email"])
        return self._build_login_challenge_response(
            challenge_id,
            payload["email"],
            str(payload.get("risk_reason") or "new_ip"),
        )

    def verify_login_challenge(self, challenge_id: str, code: str) -> dict[str, Any]:
        """完成登录二次验证并签发正式凭证。"""
        payload = self._load_login_challenge(challenge_id)

        if not self.email_service.verify_login_challenge_code(payload["email"], code):
            raise FailException("验证码错误或已过期")

        redis_client.delete(self._login_challenge_key(challenge_id))
        account = self.get_account(payload["account_id"])
        if not account:
            raise FailException("账号不存在")

        return self.issue_credential(account, skip_login_alert=True)

    def _build_oauth_only_login_message(self, account: Account) -> str:
        """为仅支持第三方登录的账号构建提示文案。"""
        oauth_bindings = self.get_account_oauths_by_account_id(account.id)
        provider_names = []
        for binding in oauth_bindings:
            provider = str(getattr(binding, "provider", "") or "").strip().lower()
            if provider == "google":
                provider_names.append("Google")
            elif provider == "github":
                provider_names.append("GitHub")

        deduplicated_provider_names: list[str] = []
        for provider_name in provider_names:
            if provider_name not in deduplicated_provider_names:
                deduplicated_provider_names.append(provider_name)

        if not deduplicated_provider_names:
            return "该账号尚未设置密码，请使用第三方登录方式登录"

        if len(deduplicated_provider_names) == 1:
            return f"该账号尚未设置密码，请使用{deduplicated_provider_names[0]}登录"

        provider_text = " / ".join(deduplicated_provider_names)
        return f"该账号尚未设置密码，请使用{provider_text}登录"

    def prepare_register(self, email: str, password: str) -> None:
        """为未注册邮箱发送注册验证码。"""
        normalized_email = self._normalize_email(email)
        account = self.get_account_by_email(normalized_email)
        if account:
            if not account.is_password_set:
                raise FailException(self._build_oauth_only_login_message(account))
            raise FailException("账号已存在，请直接登录")

        self.email_service.send_register_code(normalized_email)

    def register_by_email_code(self, email: str, password: str, code: str) -> dict[str, Any]:
        """校验注册验证码后创建账号并直接登录。"""
        normalized_email = self._normalize_email(email)
        account = self.get_account_by_email(normalized_email)
        if account:
            if not account.is_password_set:
                raise FailException(self._build_oauth_only_login_message(account))
            raise FailException("账号已存在，请直接登录")

        if not self.email_service.verify_register_code(normalized_email, code):
            raise FailException("验证码错误或已过期")

        account = self.create_account(
            email=normalized_email,
            name=normalized_email.split("@", 1)[0],
        )
        self.update_password(password, account)
        return self.begin_login(account)

    def password_login(self, email: str, password: str) -> dict[str, Any]:
        """根据传递的密码 + 邮箱登录特定的账号"""
        normalized_email = self._normalize_email(email)
        generic_error_message = "账号不存在或者密码错误"

        # 1.根据传递的邮箱查询账号是否存在
        account = self.get_account_by_email(normalized_email)
        if not account:
            raise FailException(generic_error_message)

        if not account.is_password_set:
            raise FailException(generic_error_message)

        # 2.校验账号密码是否正确
        if not compare_password(
            password,
            account.password,
            account.password_salt
        ):
            raise FailException(generic_error_message)

        # 3.根据登录风险返回授权凭证或二次验证挑战
        return self.begin_login(account)

    def send_reset_code(self, email: str) -> None:
        """发送密码重置验证码"""
        normalized_email = self._normalize_email(email)
        # 1.检查账号是否存在
        account = self.get_account_by_email(normalized_email)
        if not account:
            return

        # 2.发送验证码
        self.email_service.send_verification_code(normalized_email)

    def reset_password(self, email: str, code: str, new_password: str) -> None:
        """重置密码"""
        normalized_email = self._normalize_email(email)
        # 1.验证验证码
        if not self.email_service.verify_code(normalized_email, code):
            raise FailException("验证码错误或已过期")

        # 2.获取账号
        account = self.get_account_by_email(normalized_email)
        if not account:
            raise FailException("账号不存在")

        # 3.更新密码
        self.update_password(new_password, account)

