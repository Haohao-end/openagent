import json
from fnmatch import fnmatch
from uuid import uuid4

import pytest

from internal.entity.agent_notification_entity import AgentNotificationEntity
from internal.entity.document_index_notification_entity import (
    DocumentIndexNotificationEntity,
)
from internal.service.notification_service import NotificationService


class _FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}

    def setex(self, key, _ttl, value):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)

    def lpush(self, key, value):
        self.lists.setdefault(key, [])
        self.lists[key].insert(0, value)

    def expire(self, key, _ttl):
        return 1

    def lrange(self, key, start, end):
        items = self.lists.get(key, [])
        if end == -1:
            return items[start:]
        return items[start : end + 1]

    def lrem(self, key, _count, value):
        self.lists[key] = [item for item in self.lists.get(key, []) if item != value]

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.lists.pop(key, None)

    def keys(self, pattern):
        candidates = list(self.values.keys()) + list(self.lists.keys())
        return [key for key in candidates if fnmatch(key, pattern)]


@pytest.fixture
def fake_redis(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr("internal.service.notification_service.redis_client", redis)
    return redis


@pytest.fixture
def notification_service(fake_redis):
    return NotificationService()


def test_create_and_get_document_index_notification(notification_service):
    user_id = uuid4()
    dataset_id = uuid4()
    document_id = uuid4()

    notification = notification_service.create_notification(
        user_id=user_id,
        dataset_id=dataset_id,
        document_id=document_id,
        document_name="test_doc.pdf",
        segment_count=10,
        index_duration=5.5,
        status="success",
    )

    assert notification.id is not None
    assert notification.dataset_id == dataset_id
    assert notification.document_name == "test_doc.pdf"

    retrieved = notification_service._get_notification(notification.id)
    assert isinstance(retrieved, DocumentIndexNotificationEntity)
    assert retrieved.dataset_id == dataset_id
    assert retrieved.document_name == "test_doc.pdf"


def test_create_and_get_agent_notification(notification_service):
    user_id = uuid4()
    app_id = uuid4()

    notification = notification_service.create_agent_notification(
        user_id=user_id,
        app_id=app_id,
        app_name="Test Agent",
    )

    assert notification.id is not None
    assert notification.app_id == app_id
    assert notification.app_name == "Test Agent"

    retrieved = notification_service._get_notification(notification.id)
    assert isinstance(retrieved, AgentNotificationEntity)
    assert retrieved.app_id == app_id
    assert retrieved.app_name == "Test Agent"


def test_get_user_notifications_mixed_types(notification_service):
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

    notifications, total = notification_service.get_user_notifications(user_id, limit=10)

    assert total == 2
    assert len(notifications) == 2
    assert {type(item).__name__ for item in notifications} == {
        "AgentNotificationEntity",
        "DocumentIndexNotificationEntity",
    }


def test_get_user_notifications_supports_type_filter(notification_service):
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
    assert isinstance(document_notifications[0], DocumentIndexNotificationEntity)
    assert agent_total == 1
    assert isinstance(agent_notifications[0], AgentNotificationEntity)


def test_notification_redis_data_structure(notification_service, fake_redis):
    user_id = uuid4()
    app_id = uuid4()

    notification = notification_service.create_agent_notification(
        user_id=user_id,
        app_id=app_id,
        app_name="Test Agent",
    )

    notification_key = f"notification:{notification.id}"
    data = fake_redis.get(notification_key)
    assert data is not None

    notification_data = json.loads(data)
    assert notification_data["app_id"] == str(app_id)
    assert notification_data["app_name"] == "Test Agent"
    assert "dataset_id" not in notification_data
