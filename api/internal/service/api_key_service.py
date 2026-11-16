import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID
from injector import inject
from dataclasses import dataclass

from sqlalchemy import case, desc, func, or_

from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from internal.schema.api_key_schema import CreateApiKeyReq
from internal.model import Account, ApiKey
from internal.model.api_key import API_KEY_SCOPE_OPENAPI_CHAT, API_KEY_SUPPORTED_SCOPES
from internal.exception import ForbiddenException
from internal.lib.helper import ensure_utc_naive, utc_now_naive
from pkg.paginator import PaginatorReq, Paginator

_LAST_USED_AT_UPDATE_INTERVAL = timedelta(minutes=1)
_ALLOWED_UPDATE_FIELDS = frozenset({"is_active", "remark", "expires_at", "scopes"})
logger = logging.getLogger(__name__)

@inject
@dataclass
class ApiKeyService(BaseService):
    """API密钥服务"""
    db: SQLAlchemy

    def create_api_key(self, req: CreateApiKeyReq, account: Account) -> dict[str, str]:
        """根据传递的信息创建API密钥，明文只在创建时返回一次。"""
        raw_api_key = self.generate_api_key()
        scopes_field = getattr(req, "scopes", None)
        scopes = getattr(scopes_field, "data", None)
        scopes = self._normalize_scopes(scopes)
        api_key_record = self.create(
            ApiKey,
            account_id=account.id,
            api_key=self.hash_api_key(raw_api_key),
            is_active=req.is_active.data,
            remark=req.remark.data,
            expires_at=self._normalize_expires_at(req.expires_at.data),
            scopes=scopes,
        )
        api_key_record_id = getattr(api_key_record, "id", None)
        return {
            "id": str(api_key_record_id) if api_key_record_id else "",
            "api_key": raw_api_key,
        }

    def get_api_by_by_credential(self, api_key: str) -> ApiKey | None:
        """根据传递的凭证信息获取ApiKey记录"""
        if not api_key or not isinstance(api_key, str) or not api_key.strip():
            return None

        hashed_api_key = self.hash_api_key(api_key.strip())
        api_key_record = self.db.session.query(ApiKey).filter(
            ApiKey.api_key == hashed_api_key,
        ).one_or_none()
        if api_key_record:
            return api_key_record

        # 兼容历史明文密钥，并在首次命中时自动升级为哈希存储。
        legacy_api_key_record = self.db.session.query(ApiKey).filter(
            ApiKey.api_key == api_key,
        ).one_or_none()
        if legacy_api_key_record and legacy_api_key_record.api_key != hashed_api_key:
            try:
                legacy_api_key_record.api_key = hashed_api_key
                if hasattr(self.db.session, "commit"):
                    self.db.session.commit()
            except Exception as error:
                if hasattr(self.db.session, "rollback"):
                    self.db.session.rollback()
                logger.warning(
                    "legacy_api_key_upgrade_failed error_class=%s",
                    type(error).__name__,
                )

        return legacy_api_key_record

    def record_last_used_at(self, api_key_record: ApiKey) -> None:
        """Persist successful use at most once per minute without moving backward."""
        if not api_key_record:
            return
        api_key_id = getattr(api_key_record, "id", None)
        if not api_key_id:
            return
        used_at = utc_now_naive()
        update_after = used_at - _LAST_USED_AT_UPDATE_INTERVAL
        with self.db.auto_commit():
            self.db.session.query(ApiKey).filter(
                ApiKey.id == api_key_id,
                or_(ApiKey.last_used_at.is_(None), ApiKey.last_used_at <= update_after),
            ).update(
                {ApiKey.last_used_at: used_at},
                synchronize_session=False,
            )

    def record_api_key_request(self, api_key_record: ApiKey) -> None:
        """Count one authorized OpenAPI request and refresh last-used metadata."""
        if not api_key_record:
            return
        api_key_id = getattr(api_key_record, "id", None)
        if not api_key_id:
            return
        used_at = utc_now_naive()
        update_after = used_at - _LAST_USED_AT_UPDATE_INTERVAL
        last_used_is_stale = or_(
            ApiKey.last_used_at.is_(None),
            ApiKey.last_used_at <= update_after,
        )
        with self.db.auto_commit():
            self.db.session.query(ApiKey).filter(
                ApiKey.id == api_key_id,
            ).update(
                {
                    ApiKey.request_count: func.coalesce(ApiKey.request_count, 0) + 1,
                    ApiKey.last_used_at: case(
                        (last_used_is_stale, used_at),
                        else_=ApiKey.last_used_at,
                    ),
                },
                synchronize_session=False,
            )

    def get_api_key(self, api_key_id: UUID, account: Account) -> ApiKey:
        """根据传递的密钥id+账号信息获取记录"""
        api_key = self.get(ApiKey, api_key_id)
        if not api_key or api_key.account_id != account.id:
            raise ForbiddenException("API密钥不存在或无权限")
        return api_key

    def update_api_key(self, api_key_id: UUID, account: Account, **kwargs) -> ApiKey:
        """根据传递的信息更新API密钥"""
        api_key = self.get_api_key(api_key_id, account)
        updates = {k: v for k, v in kwargs.items() if k in _ALLOWED_UPDATE_FIELDS}
        if "expires_at" in updates:
            updates["expires_at"] = self._normalize_expires_at(updates["expires_at"])
        if "scopes" in updates:
            updates["scopes"] = self._normalize_scopes(updates["scopes"])
        if updates:
            self.update(api_key, **updates)
        return api_key

    @staticmethod
    def _normalize_scopes(scopes: object) -> list[str]:
        """Validate and normalize scopes against supported scope set."""
        if scopes is None:
            return [API_KEY_SCOPE_OPENAPI_CHAT]
        if not isinstance(scopes, (list, tuple)) or any(not isinstance(s, str) for s in scopes):
            raise ValueError("API key scopes must be a list of strings")
        if len(scopes) != len(set(scopes)):
            raise ValueError("API key scopes cannot contain duplicates")
        if not set(scopes).issubset(API_KEY_SUPPORTED_SCOPES):
            raise ValueError("API key scopes contain unsupported scope")
        return list(scopes)

    @staticmethod
    def _normalize_expires_at(value: int | datetime | None) -> datetime | None:
        """Convert API timestamps to the naive UTC value used by database columns."""
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("API key expiration must be a Unix timestamp")
        if isinstance(value, int):
            value = datetime.fromtimestamp(value, UTC)
        if not isinstance(value, datetime):
            raise ValueError("API key expiration must be a Unix timestamp")
        return ensure_utc_naive(value)

    def delete_api_key(self, api_key_id: UUID, account: Account) -> ApiKey:
        """根据传递的id删除API密钥"""
        api_key = self.get_api_key(api_key_id, account)
        self.delete(api_key)
        return api_key

    def get_api_keys_with_page(self, req: PaginatorReq, account: Account) -> tuple[list[ApiKey], Paginator]:
        """根据传递的信息获取API密钥分页列表数据"""
        # 1.构建分页器
        paginator = Paginator(db=self.db, req=req)

        # 2.执行分页并获取数据
        api_keys = paginator.paginate(
            self.db.session.query(ApiKey).filter(
                ApiKey.account_id == account.id,
            ).order_by(desc(ApiKey.created_at), desc(ApiKey.id))
        )

        return api_keys, paginator
    @classmethod
    def generate_api_key(cls, api_key_prefix: str = "llmops-v1/") -> str:
        """生成一个长度为48的API密钥,并携带前缀"""
        return api_key_prefix + secrets.token_urlsafe(48)

    @classmethod
    def hash_api_key(cls, api_key: str) -> str:
        """对 API Key 做 SHA-256 哈希后存储。"""
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
