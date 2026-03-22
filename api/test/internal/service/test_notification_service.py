"""通知服务测试"""
import json
from uuid import uuid4
from datetime import datetime, UTC

import pytest
from internal.service.notification_service import NotificationService
from internal.entity.document_index_notification_entity import DocumentIndexNotificationEntity
from internal.entity.agent_notification_entity import AgentNotificationEntity
from internal.extension.redis_extension import redis_client


@pytest.fixture
def notification_service():
    """创建通知服务实例"""
    return NotificationService()


@pytest.fixture(autouse=True)
def cleanup_redis():
    """清理 Redis 中的测试数据"""
    yield
    # 清理所有通知相关的 key
    keys = redis_client.keys("notification:*")
    if keys:
        redis_client.delete(*keys)
    keys = redis_client.keys("user_notifications:*")
    if keys:
        redis_client.delete(*keys)
    keys = redis_client.keys("user_document_notifications:*")
    if keys:
        redis_client.delete(*keys)
    keys = redis_client.keys("user_agent_notifications:*")
    if keys:
        redis_client.delete(*keys)


def test_create_and_get_document_index_notification(notification_service):
    """测试创建和获取文档索引通知"""
    user_id = uuid4()
    dataset_id = uuid4()
    document_id = uuid4()

    # 创建文档索引通知
    notification = notification_service.create_notification(
        user_id=user_id,
        dataset_id=dataset_id,
        document_id=document_id,
        document_name="test_doc.pdf",
        segment_count=10,
        index_duration=5.5,
        status="success",
    )

    # 验证通知被正确创建
    assert notification.id is not None
    assert notification.dataset_id == dataset_id
    assert notification.document_name == "test_doc.pdf"

    # 从 Redis 获取通知
    retrieved = notification_service._get_notification(notification.id)
    assert retrieved is not None
    assert isinstance(retrieved, DocumentIndexNotificationEntity)
    assert retrieved.dataset_id == dataset_id
    assert retrieved.document_name == "test_doc.pdf"


def test_create_and_get_agent_notification(notification_service):
    """测试创建和获取 Agent 通知"""
    user_id = uuid4()
    app_id = uuid4()

    # 创建 Agent 通知
    notification = notification_service.create_agent_notification(
        user_id=user_id,
        app_id=app_id,
        app_name="Test Agent",
    )

    # 验证通知被正确创建
    assert notification.id is not None
    assert notification.app_id == app_id
    assert notification.app_name == "Test Agent"

    # 从 Redis 获取通知
    retrieved = notification_service._get_notification(notification.id)
    assert retrieved is not None
    assert isinstance(retrieved, AgentNotificationEntity)
    assert retrieved.app_id == app_id
    assert retrieved.app_name == "Test Agent"


def test_get_user_notifications_mixed_types(notification_service):
    """测试获取混合类型的用户通知"""
    user_id = uuid4()
    dataset_id = uuid4()
    document_id = uuid4()
    app_id = uuid4()

    # 创建文档索引通知
    doc_notification = notification_service.create_notification(
        user_id=user_id,
        dataset_id=dataset_id,
        document_id=document_id,
        document_name="test_doc.pdf",
        segment_count=10,
        index_duration=5.5,
        status="success",
    )

    # 创建 Agent 通知
    agent_notification = notification_service.create_agent_notification(
        user_id=user_id,
        app_id=app_id,
        app_name="Test Agent",
    )

    # 获取用户的所有通知
    notifications, total = notification_service.get_user_notifications(user_id, limit=10)

    # 验证获取到两个通知
    assert total == 2
    assert len(notifications) == 2

    # 验证通知类型正确
    types = [type(n).__name__ for n in notifications]
    assert "AgentNotificationEntity" in types
    assert "DocumentIndexNotificationEntity" in types

    # 验证 Agent 通知的字段
    agent_notif = next(n for n in notifications if isinstance(n, AgentNotificationEntity))
    assert agent_notif.app_id == app_id
    assert agent_notif.app_name == "Test Agent"

    # 验证文档通知的字段
    doc_notif = next(n for n in notifications if isinstance(n, DocumentIndexNotificationEntity))
    assert doc_notif.dataset_id == dataset_id
    assert doc_notif.document_name == "test_doc.pdf"


def test_get_user_notifications_supports_type_filter(notification_service):
    """测试按通知类型过滤"""
    user_id = uuid4()
    dataset_id = uuid4()
    document_id = uuid4()
    app_id = uuid4()

    notification_service.create_notification(
        user_id=user_id,
        dataset_id=dataset_id,
        document_id=document_id,
        document_name="test_doc.pdf",
        segment_count=10,
        index_duration=5.5,
        status="success",
    )
    notification_service.create_agent_notification(
        user_id=user_id,
        app_id=app_id,
        app_name="Test Agent",
    )

    document_notifications, document_total = notification_service.get_user_notifications(
        user_id, limit=10, notification_type="document"
    )
    agent_notifications, agent_total = notification_service.get_user_notifications(
        user_id, limit=10, notification_type="agent"
    )

    assert document_total == 1
    assert len(document_notifications) == 1
    assert isinstance(document_notifications[0], DocumentIndexNotificationEntity)

    assert agent_total == 1
    assert len(agent_notifications) == 1
    assert isinstance(agent_notifications[0], AgentNotificationEntity)


def test_notification_redis_data_structure(notification_service):
    """测试通知在 Redis 中的数据结构"""
    user_id = uuid4()
    app_id = uuid4()

    # 创建 Agent 通知
    notification = notification_service.create_agent_notification(
        user_id=user_id,
        app_id=app_id,
        app_name="Test Agent",
    )

    # 直接从 Redis 读取数据
    notification_key = f"notification:{notification.id}"
    data = redis_client.get(notification_key)
    assert data is not None

    notification_data = json.loads(data)

    # 验证 Redis 中的数据结构
    assert "app_id" in notification_data
    assert "app_name" in notification_data
    assert notification_data["app_id"] == str(app_id)
    assert notification_data["app_name"] == "Test Agent"
    assert "dataset_id" not in notification_data  # Agent 通知不应该有 dataset_id
