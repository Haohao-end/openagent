import logging
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID
from injector import inject
from redis import Redis
from sqlalchemy import desc, asc, func
from internal.entity.cache_entity import LOCK_DOCUMENT_UPDATE_ENABLED, LOCK_EXPIRE_TIME
from internal.entity.dataset_entity import ProcessType, DocumentStatus, SegmentStatus
from internal.entity.upload_file_entity import ALLOWED_DOCUMENT_EXTENSION
from internal.exception import ForbiddenException, FailException, NotFoundException, ValidateErrorException
from internal.lib.helper import datetime_to_timestamp
from internal.model import Dataset, Document, Segment, UploadFile, ProcessRule, Account
from internal.schema.document_schema import GetDocumentsWithPageReq
from internal.task.document_task import build_documents, update_document_enabled, delete_document
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


_DOCUMENT_ALLOWED_UPDATE_FIELDS = frozenset({"name"})


@inject
@dataclass
class DocumentService(BaseService):
    """文档服务"""
    db: SQLAlchemy
    redis_client: Redis

    def create_documents(
            self,
            dataset_id: UUID,
            upload_file_ids: list[UUID],
            process_type: str = ProcessType.AUTOMATIC.value,
            rule: dict = None,
            account: Account = None,
    ) -> tuple[list[Document], str]:
        """根据传递的信息创建文档列表并调用异步任务"""
        # 1.检测知识库权限
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise ForbiddenException("当前用户无该知识库权限或知识库不存在")

        # 2.提取文件并校验文件权限与文件扩展
        upload_files = self.db.session.query(UploadFile).filter(
            UploadFile.account_id == account.id,
            UploadFile.id.in_(upload_file_ids),
        ).all()

        upload_files = [
            upload_file for upload_file in upload_files
            if upload_file.extension.lower() in ALLOWED_DOCUMENT_EXTENSION
        ]

        if len(upload_files) == 0:
            logging.warning(
                f"上传文档列表未解析到合法文件，account_id: {str(account.id)}, dataset_id: {dataset_id}, upload_file_ids: {upload_file_ids}"
            )
            raise FailException("暂未解析到合法文件，请重新上传")

        # 3.创建批次与处理规则，并在同一事务中写入全部文档记录
        batch = time.strftime("%Y%m%d%H%M%S") + str(random.randint(100000, 999999))
        position = self.get_latest_document_position(dataset_id)
        documents: list[Document] = []
        with self.db.auto_commit():
            process_rule = ProcessRule(
                account_id=account.id,
                dataset_id=dataset_id,
                mode=process_type,
                rule=rule,
            )
            self.db.session.add(process_rule)
            self.db.session.flush()

            for upload_file in upload_files:
                position += 1
                document = Document(
                    account_id=account.id,
                    dataset_id=dataset_id,
                    upload_file_id=upload_file.id,
                    process_rule_id=process_rule.id,
                    batch=batch,
                    name=upload_file.name,
                    position=position,
                )
                self.db.session.add(document)
                documents.append(document)
            self.db.session.flush()

        # 4.调用异步任务，完成后续操作
        build_documents.delay([document.id for document in documents])

        # 5.返回文档列表与处理批次
        return documents, batch

    def get_documents_status(self, dataset_id: UUID, batch: str, account: Account) -> list[dict]:
        """根据传递的知识库id+处理批次获取文档列表的状态"""
        # 1.检测知识库权限
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise ForbiddenException("当前用户无该知识库权限或知识库不存在")

        # 2.查询当前知识库下该批次的文档列表
        documents = self.db.session.query(Document).filter(
            Document.dataset_id == dataset_id,
            Document.batch == batch,
        ).order_by(asc("position")).all()
        if documents is None or len(documents) == 0:
            raise NotFoundException("该处理批次未发现文档，请核实后重试")

        # 3.批量查询片段数、已完成片段数及上传文件，消除 N+1 查询
        doc_ids = [doc.id for doc in documents]
        segment_counts = dict(
            self.db.session.query(Segment.document_id, func.count(Segment.id))
            .filter(Segment.document_id.in_(doc_ids))
            .group_by(Segment.document_id)
            .all()
        )
        completed_counts = dict(
            self.db.session.query(Segment.document_id, func.count(Segment.id))
            .filter(Segment.document_id.in_(doc_ids), Segment.status == SegmentStatus.COMPLETED.value)
            .group_by(Segment.document_id)
            .all()
        )
        upload_file_ids = [doc.upload_file_id for doc in documents if getattr(doc, "upload_file_id", None)]
        upload_files = {
            uf.id: uf
            for uf in self.db.session.query(UploadFile).filter(UploadFile.id.in_(upload_file_ids)).all()
        } if upload_file_ids else {}

        # 4.循环遍历文档列表提取文档的状态信息
        documents_status = []
        for document in documents:
            upload_file = upload_files.get(getattr(document, "upload_file_id", None))
            if upload_file is None:
                upload_file = getattr(document, "upload_file", None)

            documents_status.append({
                "id": document.id,
                "name": document.name,
                "size": getattr(upload_file, "size", 0) if upload_file else 0,
                "extension": getattr(upload_file, "extension", "") if upload_file else "",
                "mime_type": getattr(upload_file, "mime_type", "") if upload_file else "",
                "position": document.position,
                "segment_count": segment_counts.get(document.id, 0),
                "completed_segment_count": completed_counts.get(document.id, 0),
                "error": document.error,
                "status": document.status,
                "processing_started_at": datetime_to_timestamp(document.processing_started_at),
                "parsing_completed_at": datetime_to_timestamp(document.parsing_completed_at),
                "splitting_completed_at": datetime_to_timestamp(document.splitting_completed_at),
                "indexing_completed_at": datetime_to_timestamp(document.indexing_completed_at),
                "completed_at": datetime_to_timestamp(document.completed_at),
                "stopped_at": datetime_to_timestamp(document.stopped_at),
                "created_at": datetime_to_timestamp(document.created_at),
            })

        return documents_status

    def get_document(self, dataset_id: UUID, document_id: UUID, account: Account) -> Document:
        """根据传递的知识库id+文档id获取文档记录信息"""
        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("该文档不存在，请核实后重试")
        if document.dataset_id != dataset_id or document.account_id != account.id:
            raise ForbiddenException("当前用户获取该文档，请核实后重试")

        return document

    def update_document(self, dataset_id: UUID, document_id: UUID, account: Account, **kwargs) -> Document:
        """根据传递的知识库id+文档id，更新文档信息"""
        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("该文档不存在，请核实后重试")
        if document.dataset_id != dataset_id or document.account_id != account.id:
            raise ForbiddenException("当前用户无权限修改该文档，请核实后重试")

        updates = {k: v for k, v in kwargs.items() if k in _DOCUMENT_ALLOWED_UPDATE_FIELDS}
        if "name" in updates:
            name = str(updates["name"] or "").strip()
            if not name:
                raise ValidateErrorException("文档名称不能为空")
            if len(name) > 100:
                raise ValidateErrorException("文档的名称长度不能超过100")
            updates["name"] = name

        if updates:
            self.update(document, **updates)

        return document

    def update_document_enabled(
            self,
            dataset_id: UUID,
            document_id: UUID,
            enabled: bool,
            account: Account,
    ) -> Document:
        """根据传递的知识库id+文档id，更新文档的启用状态，同时会异步更新weaviate向量数据库中的数据"""
        # 1.获取文档并校验权限
        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("该文档不存在，请核实后重试")
        if document.dataset_id != dataset_id or document.account_id != account.id:
            raise ForbiddenException("当前用户无权限修改该知识库下的文档，请核实后重试")

        # 2.判断文档是否处于可以修改的状态，只有构建完成才可以修改enabled
        if document.status != DocumentStatus.COMPLETED.value:
            raise ForbiddenException("当前文档处于不可修改状态，请稍后重试")

        # 3.判断修改的启用状态是否正确，需与当前的状态相反
        if document.enabled == enabled:
            raise FailException(f"文档状态修改错误，当前已是{'启用' if enabled else '禁用'}状态")

        # 4.原子获取更新文档启用状态的锁
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document.id)
        if not self.redis_client.set(cache_key, 1, ex=LOCK_EXPIRE_TIME, nx=True):
            raise FailException("当前文档正在修改启用状态，请稍后再次尝试")
        original_state = (document.enabled, getattr(document, "disabled_at", None))

        # 5.修改文档的启用状态
        try:
            self.update(
                document,
                enabled=enabled,
                disabled_at=None if enabled else datetime.now(UTC),
            )
        except Exception:
            self.redis_client.delete(cache_key)
            raise

        # 6.启用异步任务完成后续操作
        try:
            update_document_enabled.delay(document.id)
        except Exception:
            try:
                self.update(document, enabled=original_state[0], disabled_at=original_state[1])
            finally:
                self.redis_client.delete(cache_key)
            raise

        return document

    def delete_document(self, dataset_id: UUID, document_id: UUID, account: Account) -> Document:
        """根据传递的知识库id+文档id删除文档信息，涵盖：文档片段删除、关键词表更新、weaviate向量数据库记录删除"""
        # 1.获取文档并校验权限
        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("该文档不存在，请核实后重试")
        if document.dataset_id != dataset_id or document.account_id != account.id:
            raise ForbiddenException("当前用户无权限删除该知识库下的文档，请核实后重试")

        # 2.判断文档是否处于可删除状态，只有构建完成/出错的时候才可以删除，其他情况需要等待构建完成
        if document.status not in [DocumentStatus.COMPLETED.value, DocumentStatus.ERROR.value]:
            raise FailException("当前文档处于不可删除状态，请稍后重试")

        # 3.删除postgres中的文档基础信息
        self.delete(document)

        # 4.调用异步任务执行后续操作，涵盖：关键词表更新、片段数据删除、weaviate记录删除等
        delete_document.delay(dataset_id, document_id)

        return document

    def get_documents_with_page(
            self, dataset_id: UUID, req: GetDocumentsWithPageReq, account: Account,
    ) -> tuple[list[Document], Paginator]:
        """根据传递的知识库id+请求数据获取文档分页列表数据"""
        # 1.获取知识库并校验权限
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise NotFoundException("该知识库不存在，或无权限")

        # 2.构建分页查询器
        paginator = Paginator(db=self.db, req=req)

        # 3.构建筛选器
        filters = [
            Document.account_id == account.id,
            Document.dataset_id == dataset_id,
        ]
        if req.search_word.data:
            filters.append(Document.name.ilike(f"%{req.search_word.data}%"))

        # 4.执行分页并获取数据
        documents = paginator.paginate(
            self.db.session.query(Document).filter(*filters).order_by(
                desc(Document.created_at), desc(Document.id),
            )
        )

        # 5.批量预加载当前页文档命中次数，消除序列化时的 N+1 查询
        doc_ids = [doc.id for doc in documents if hasattr(doc, "id")]
        if doc_ids:
            hit_counts = dict(
                self.db.session.query(
                    Segment.document_id,
                    func.coalesce(func.sum(Segment.hit_count), 0),
                )
                .filter(Segment.document_id.in_(doc_ids))
                .group_by(Segment.document_id)
                .all()
            )
            for doc in documents:
                if hasattr(doc, "id"):
                    doc._hit_count = int(hit_counts.get(doc.id, 0))

        return documents, paginator

    def get_latest_document_position(self, dataset_id: UUID) -> int:
        """根据传递的知识库id获取最新文档位置"""
        document = self.db.session.query(Document).filter(
            Document.dataset_id == dataset_id,
        ).order_by(desc("position")).first()
        return document.position if document else 0
