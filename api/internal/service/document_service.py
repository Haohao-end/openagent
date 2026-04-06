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
from internal.exception import ForbiddenException, FailException, NotFoundException
from internal.lib.helper import datetime_to_timestamp
from internal.model import Dataset, Document, Segment, UploadFile, ProcessRule, Account
from internal.schema.document_schema import GetDocumentsWithPageReq
from internal.task.document_task import build_documents, update_document_enabled, delete_document
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


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

        # 3.创建批次与处理规则并记录到数据库中
        batch = time.strftime("%Y%m%d%H%M%S") + str(random.randint(100000, 999999))
        process_rule = self.create(
            ProcessRule,
            account_id=account.id,
            dataset_id=dataset_id,
            mode=process_type,
            rule=rule,
        )

        # 4.获取当前知识库的最新文档位置
        position = self.get_latest_document_position(dataset_id)

        # 5.循环遍历所有合法的上传文件列表并记录
        documents = []
        for upload_file in upload_files:
            position += 1
            document = self.create(
                Document,
                account_id=account.id,
                dataset_id=dataset_id,
                upload_file_id=upload_file.id,
                process_rule_id=process_rule.id,
                batch=batch,
                name=upload_file.name,
                position=position,
            )
            documents.append(document)

        # 6.调用异步任务，完成后续操作
        build_documents.delay([document.id for document in documents])

        # 7.返回文档列表与处理批次
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

        # 3.循环遍历文档列表提取文档的状态信息
        documents_status = []
        for document in documents:
            # 4.查询每个文档的总片段数和已构建完成的片段数
            segment_count = self.db.session.query(func.count(Segment.id)).filter(
                Segment.document_id == document.id,
            ).scalar()
            completed_segment_count = self.db.session.query(func.count(Segment.id)).filter(
                Segment.document_id == document.id,
                Segment.status == SegmentStatus.COMPLETED.value,
            ).scalar()

            upload_file = document.upload_file
            documents_status.append({
                "id": document.id,
                "name": document.name,
                "size": upload_file.size,
                "extension": upload_file.extension,
                "mime_type": upload_file.mime_type,
                "position": document.position,
                "segment_count": segment_count,
                "completed_segment_count": completed_segment_count,
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

        return self.update(document, **kwargs)

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

        # 4.获取更新文档启用状态的缓存键并检测是否上锁
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document.id)
        cache_result = self.redis_client.get(cache_key)
        if cache_result is not None:
            raise FailException("当前文档正在修改启用状态，请稍后再次尝试")

        # 5.修改文档的启用状态并设置缓存键，缓存时间为600s
        self.update(
            document,
            enabled=enabled,
            disabled_at=None if enabled else datetime.now(UTC),
        )
        self.redis_client.setex(cache_key, LOCK_EXPIRE_TIME, 1)

        # 6.启用异步任务完成后续操作
        update_document_enabled.delay(document.id)

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
            self.db.session.query(Document).filter(*filters).order_by(desc("created_at"))
        )

        return documents, paginator

    def get_latest_document_position(self, dataset_id: UUID) -> int:
        """根据传递的知识库id获取最新文档位置"""
        document = self.db.session.query(Document).filter(
            Document.dataset_id == dataset_id,
        ).order_by(desc("position")).first()
        return document.position if document else 0
