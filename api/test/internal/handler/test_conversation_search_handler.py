import pytest
from uuid import uuid4
from internal.model import Account, Conversation, Message, App
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from pkg.response import HttpCode


class TestConversationSearchHandler:
    """对话搜索处理器的测试类"""

    @pytest.fixture
    def http_client(self, app):
        """使用独立客户端，避免触发全局 client->db 自动事务夹具。"""
        with app.test_client() as client:
            yield client

    def test_search_conversations_empty_query(self, http_client, login_account, db):
        """测试空查询返回最近会话"""
        # 创建测试应用
        app = App(
            id=uuid4(),
            account_id=login_account.id,
            name="测试应用",
        )
        db.session.add(app)
        db.session.flush()

        # 创建测试会话和消息
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="测试会话",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            created_by=login_account.id,
            query="你好",
            answer="你好，我是助手",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 测试空查询
        resp = http_client.get("/conversations/search", query_string={"query": "", "limit": 10})

        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        data = resp.json.get("data", [])
        assert len(data) > 0
        assert data[0]["name"] == "测试会话"

    def test_search_conversations_by_query_text(self, http_client, login_account, db):
        """测试按查询文本搜索"""
        # 创建测试应用
        app = App(
            id=uuid4(),
            account_id=login_account.id,
            name="测试应用",
        )
        db.session.add(app)
        db.session.flush()

        # 创建测试会话和消息
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="Python教程",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            created_by=login_account.id,
            query="如何学习Python",
            answer="Python是一门很好的编程语言",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 测试搜索
        resp = http_client.get("/conversations/search", query_string={"query": "Python", "limit": 10})

        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        data = resp.json.get("data", [])
        assert len(data) > 0
        assert "Python" in data[0]["name"] or "Python" in data[0]["matched_query"]

    def test_search_conversations_by_answer_text(self, http_client, login_account, db):
        """测试按答案文本搜索"""
        # 创建测试应用
        app = App(
            id=uuid4(),
            account_id=login_account.id,
            name="测试应用",
        )
        db.session.add(app)
        db.session.flush()

        # 创建测试会话和消息
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="测试会话",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            created_by=login_account.id,
            query="什么是机器学习",
            answer="机器学习是人工智能的一个重要分支",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 测试搜索
        resp = http_client.get("/conversations/search", query_string={"query": "机器学习", "limit": 10})

        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        data = resp.json.get("data", [])
        assert len(data) > 0

    def test_search_conversations_no_results(self, http_client, login_account, db):
        """测试搜索无结果"""
        # 创建测试应用
        app = App(
            id=uuid4(),
            account_id=login_account.id,
            name="测试应用",
        )
        db.session.add(app)
        db.session.flush()

        # 创建测试会话和消息
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="测试会话",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            created_by=login_account.id,
            query="你好",
            answer="你好，我是助手",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 测试搜索不存在的内容
        resp = http_client.get("/conversations/search", query_string={"query": "不存在的内容xyz", "limit": 10})

        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        data = resp.json.get("data", [])
        assert len(data) == 0

    def test_search_conversations_limit_validation(self, http_client, login_account):
        """测试limit参数验证"""
        # 测试limit超过最大值
        resp = http_client.get("/conversations/search", query_string={"query": "test", "limit": 200})

        assert resp.status_code == 200
        # 应该被限制到100
        assert resp.json.get("code") == HttpCode.SUCCESS

    def test_search_conversations_only_own_conversations(self, http_client, login_account, db):
        """测试只能搜索自己的会话"""
        # 创建测试应用
        app = App(
            id=uuid4(),
            account_id=login_account.id,
            name="测试应用",
        )
        db.session.add(app)
        db.session.flush()

        # 创建另一个账号
        other_account = Account(
            id=uuid4(),
            email="other@example.com",
            name="Other User",
        )
        db.session.add(other_account)
        db.session.flush()

        # 创建其他账号的应用
        other_app = App(
            id=uuid4(),
            account_id=other_account.id,
            name="其他应用",
        )
        db.session.add(other_app)
        db.session.flush()

        # 创建其他账号的会话
        other_conversation = Conversation(
            id=uuid4(),
            created_by=other_account.id,
            name="其他用户的会话",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=other_app.id,
        )
        db.session.add(other_conversation)
        db.session.flush()

        other_message = Message(
            id=uuid4(),
            conversation_id=other_conversation.id,
            created_by=other_account.id,
            query="其他用户的查询",
            answer="其他用户的答案",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(other_message)
        db.session.commit()

        # 当前用户搜索不应该看到其他用户的会话
        resp = http_client.get("/conversations/search", query_string={"query": "其他用户", "limit": 10})

        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        data = resp.json.get("data", [])
        # 不应该包含其他用户的会话
        assert not any(conv["id"] == str(other_conversation.id) for conv in data)

    def test_search_conversations_by_conversation_name(self, http_client, login_account, db):
        """测试按会话名称搜索 - 这是修复的bug"""
        # 创建测试应用
        app = App(
            id=uuid4(),
            account_id=login_account.id,
            name="测试应用",
        )
        db.session.add(app)
        db.session.flush()

        # 创建测试会话，名称包含搜索词
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="Python编程教程",  # 会话名称包含"Python"
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        # 创建消息，但消息内容不包含"Python"
        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            created_by=login_account.id,
            query="如何开始学习编程",
            answer="首先需要选择一门编程语言",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 搜索"Python"，应该能找到这个会话（通过会话名称）
        resp = http_client.get("/conversations/search", query_string={"query": "Python", "limit": 10})

        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        data = resp.json.get("data", [])
        # 应该找到这个会话
        assert len(data) > 0
        assert any(conv["id"] == str(conversation.id) for conv in data)
