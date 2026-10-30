from uuid import UUID
from celery import shared_task

@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3}, retry_backoff=True)
def delete_dataset(dataset_id: UUID) -> None:
    """根据传递的知识库id删除特定的知识库信息"""
    from app.http.app import injector
    from internal.service import IndexingService

    indexing_service = injector.get(IndexingService)
    indexing_service.delete_dataset(dataset_id)
