from uuid import UUID
from celery import shared_task
from datetime import datetime, UTC
import logging

@shared_task
def build_documents(document_ids: list[UUID]) -> None:
    """根据传递的文档id列表 构建文档"""
    from app.http.app import injector
    from internal.service.indexing_service import IndexingService
    from internal.service.notification_service import NotificationService
    from internal.model import Document
    from pkg.sqlalchemy import SQLAlchemy

    indexing_service = injector.get(IndexingService)
    notification_service = injector.get(NotificationService)
    db = injector.get(SQLAlchemy)

    # 记录开始时间
    start_time = datetime.now(UTC)

    try:
        # 执行文档索引
        indexing_service.build_documents(document_ids)

        # 计算索引耗时
        end_time = datetime.now(UTC)
        index_duration = (end_time - start_time).total_seconds()

        # 为每个完成的文档创建通知
        for document_id in document_ids:
            try:
                document = db.session.query(Document).filter(Document.id == document_id).first()
                if document and document.status == "completed":
                    # 创建成功通知
                    notification = notification_service.create_notification(
                        user_id=document.account_id,
                        dataset_id=document.dataset_id,
                        document_id=document.id,
                        document_name=document.name,
                        segment_count=document.segment_count,
                        index_duration=index_duration,
                        status="success",
                        error_message="",
                    )

                    # 通过 WebSocket 推送通知
                    from internal.lib.websocket_manager import ws_manager
                    from internal.schema.document_index_notification_schema import DocumentIndexNotificationSchema

                    schema = DocumentIndexNotificationSchema()
                    notification_data = schema.dump(notification)
                    ws_manager.emit_notification_to_user(str(document.account_id), notification_data)

                    logging.info(f"Created and emitted notification for document {document_id}")
                elif document and document.status == "error":
                    # 创建错误通知
                    notification = notification_service.create_notification(
                        user_id=document.account_id,
                        dataset_id=document.dataset_id,
                        document_id=document.id,
                        document_name=document.name,
                        segment_count=0,
                        index_duration=index_duration,
                        status="error",
                        error_message=document.error or "索引失败",
                    )

                    # 通过 WebSocket 推送通知
                    from internal.lib.websocket_manager import ws_manager
                    from internal.schema.document_index_notification_schema import DocumentIndexNotificationSchema

                    schema = DocumentIndexNotificationSchema()
                    notification_data = schema.dump(notification)
                    ws_manager.emit_notification_to_user(str(document.account_id), notification_data)

                    logging.info(f"Created and emitted error notification for document {document_id}")
            except Exception as e:
                logging.error(f"Failed to create notification for document {document_id}: {e}")

    except Exception as e:
        logging.error(f"Error in build_documents task: {e}")
        raise


@shared_task
def update_document_enabled(document_id: UUID) -> None:
    """根据传递的文档id修改文档的状态"""
    from app.http.app import injector
    from internal.service.indexing_service import IndexingService

    indexing_service = injector.get(IndexingService)
    indexing_service.update_document_enabled(document_id)

@shared_task
def delete_document(dataset_id: UUID, document_id: UUID) -> None:
    """根据传递的文档id+知识库id清除文档记录"""
    from app.http.module import injector
    from internal.service.indexing_service import IndexingService

    indexing_service = injector.get(IndexingService)
    indexing_service.delete_document(dataset_id, document_id)

