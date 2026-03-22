"""通知处理器序列化逻辑测试"""
from uuid import uuid4
from datetime import datetime, UTC

import pytest
from internal.schema.document_index_notification_schema import DocumentIndexNotificationSchema
from internal.schema.agent_notification_schema import AgentNotificationSchema
from internal.entity.document_index_notification_entity import DocumentIndexNotificationEntity
from internal.entity.agent_notification_entity import AgentNotificationEntity


def test_agent_notification_serialization():
    """测试 Agent 通知序列化"""
    user_id = uuid4()
    app_id = uuid4()

    agent_notification = AgentNotificationEntity(
        id="agent-1",
        user_id=user_id,
        app_id=app_id,
        app_name="Test Agent",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        is_read=False,
    )

    schema = AgentNotificationSchema()
    serialized = schema.dump(agent_notification)

    # 验证序列化结果
    assert serialized["id"] == "agent-1"
    assert serialized["app_id"] == str(app_id)
    assert serialized["app_name"] == "Test Agent"
    assert "dataset_id" not in serialized
    assert "document_id" not in serialized


def test_document_notification_serialization():
    """测试文档索引通知序列化"""
    user_id = uuid4()
    dataset_id = uuid4()
    document_id = uuid4()

    doc_notification = DocumentIndexNotificationEntity(
        id="doc-1",
        user_id=user_id,
        dataset_id=dataset_id,
        document_id=document_id,
        document_name="test.pdf",
        segment_count=10,
        index_duration=5.5,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        status="success",
        error_message="",
        is_read=False,
    )

    schema = DocumentIndexNotificationSchema()
    serialized = schema.dump(doc_notification)

    # 验证序列化结果
    assert serialized["id"] == "doc-1"
    assert serialized["dataset_id"] == str(dataset_id)
    assert serialized["document_id"] == str(document_id)
    assert serialized["document_name"] == "test.pdf"
    assert "app_id" not in serialized
    assert "app_name" not in serialized


def test_mixed_notifications_serialization():
    """测试混合类型通知的序列化"""
    user_id = uuid4()
    dataset_id = uuid4()
    document_id = uuid4()
    app_id = uuid4()

    # 创建两种类型的通知
    doc_notification = DocumentIndexNotificationEntity(
        id="doc-1",
        user_id=user_id,
        dataset_id=dataset_id,
        document_id=document_id,
        document_name="test.pdf",
        segment_count=10,
        index_duration=5.5,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        status="success",
        error_message="",
        is_read=False,
    )

    agent_notification = AgentNotificationEntity(
        id="agent-1",
        user_id=user_id,
        app_id=app_id,
        app_name="Test Agent",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        is_read=False,
    )

    # 序列化两种通知
    notifications = [agent_notification, doc_notification]
    serialized_list = []

    for notification in notifications:
        if isinstance(notification, AgentNotificationEntity):
            schema = AgentNotificationSchema()
            serialized_list.append(schema.dump(notification))
        elif isinstance(notification, DocumentIndexNotificationEntity):
            schema = DocumentIndexNotificationSchema()
            serialized_list.append(schema.dump(notification))

    # 验证序列化结果
    assert len(serialized_list) == 2

    # 验证 Agent 通知
    agent_serialized = serialized_list[0]
    assert agent_serialized["app_name"] == "Test Agent"
    assert "dataset_id" not in agent_serialized

    # 验证文档通知
    doc_serialized = serialized_list[1]
    assert doc_serialized["document_name"] == "test.pdf"
    assert "app_id" not in doc_serialized


