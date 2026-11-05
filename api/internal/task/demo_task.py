import logging
import time
from uuid import UUID

from celery import shared_task


@shared_task
def demo_task(id: UUID) -> str:
    """测试异步任务"""
    logging.info("睡眠5秒")
    time.sleep(5)
    logging.info(f"id的值:{id}")
    return "haohao"
