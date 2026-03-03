import secrets
import hashlib
from uuid import UUID
from injector import inject
from dataclasses import dataclass

from sqlalchemy import desc

from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from internal.schema.api_key_schema import CreateApiKeyReq
from internal.model import Account, ApiKey
from internal.exception import ForbiddenException
from pkg.paginator import PaginatorReq, Paginator

@inject
@dataclass
class ApiKeyService(BaseService):
    """API密钥服务"""
    db: SQLAlchemy

    def create_api_key(self, req: CreateApiKeyReq, account: Account) -> dict[str, str]:
        """根据传递的信息创建API密钥，明文只在创建时返回一次。"""
        raw_api_key = self.generate_api_key()
        api_key_record = self.create(
            ApiKey,
            account_id=account.id,
            api_key=self.hash_api_key(raw_api_key),
            is_active=req.is_active.data,
            remark=req.remark.data,
        )
        api_key_record_id = getattr(api_key_record, "id", None)
        return {
            "id": str(api_key_record_id) if api_key_record_id else "",
            "api_key": raw_api_key,
        }

    def get_api_by_by_credential(self, api_key: str) -> ApiKey:
        """根据传递的凭证信息获取ApiKey记录"""
        hashed_api_key = self.hash_api_key(api_key)
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
            legacy_api_key_record.api_key = hashed_api_key
            if hasattr(self.db.session, "commit"):
                self.db.session.commit()

        return legacy_api_key_record

    def get_api_key(self, api_key_id: UUID, account: Account) -> ApiKey:
        """根据传递的密钥id+账号信息获取记录"""
        api_key = self.get(ApiKey, api_key_id)
        if not api_key or api_key.account_id != account.id:
            raise ForbiddenException("API密钥不存在或无权限")
        return api_key

    def update_api_key(self, api_key_id: UUID, account: Account, **kwargs) -> ApiKey:
        """根据传递的信息更新API密钥"""
        api_key = self.get_api_key(api_key_id, account)
        self.update(api_key, **kwargs)
        return api_key

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
            ).order_by(desc("created_at"))
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
