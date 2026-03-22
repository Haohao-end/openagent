"""
搜索功能的完整单元测试
测试 ConversationService.search_conversations() 方法
"""
import pytest
from uuid import uuid4
from internal.model import Account, Conversation, Message, App
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.service.conversation_service import ConversationService


class TestConversationSearchService:
    """对话搜索服务的测试类"""

    @pytest.fixture
    def service(self, db):
        """创建搜索服务实例"""
        return ConversationService(db=db)

    @pytest.fixture
    def test_app(self, login_account, db):
        """创建测试应用"""
        app = App(
            id=uuid4(),
            account_id=login_account.id,
            name="测试应用",
            icon="default_icon",
            description="测试应用描述",
            status="draft",
        )
        db.session.add(app)
        db.session.flush()
        return app

    def test_search_by_message_query(self, service, login_account, test_app, db):
        """测试按消息查询内容搜索"""
        # 创建会话
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="Python教程",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        # 创建消息
        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            app_id=test_app.id,
            created_by=login_account.id,
            query="如何学习Python",
            answer="Python是一门很好的编程语言",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 搜索"Python"
        results = service.search_conversations(login_account, "Python", limit=10)

        # 验证结果
        assert len(results) > 0, "应该找到包含'Python'的消息"
        assert results[0]["name"] == "Python教程"
        assert "Python" in results[0]["matched_query"] or "Python" in results[0]["matched_answer"]

    def test_search_by_message_answer(self, service, login_account, test_app, db):
        """测试按消息答案内容搜索"""
        # 创建会话
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="编程学习",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        # 创建消息
        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            app_id=test_app.id,
            created_by=login_account.id,
            query="什么是机器学习",
            answer="机器学习是人工智能的一个重要分支",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 搜索"机器学习"
        results = service.search_conversations(login_account, "机器学习", limit=10)

        # 验证结果
        assert len(results) > 0, "应该找到包含'机器学习'的答案"
        assert "机器学习" in results[0]["matched_answer"]

    def test_search_by_conversation_name(self, service, login_account, test_app, db):
        """测试按会话标题搜索"""
        # 创建会话（名称包含搜索词）
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="天气查询系统",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        # 创建消息
        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            app_id=test_app.id,
            created_by=login_account.id,
            query="今天天气怎么样",
            answer="今天天气晴朗",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 搜索"天气"
        results = service.search_conversations(login_account, "天气", limit=10)

        # 验证结果
        assert len(results) > 0, "应该找到会话名称包含'天气'的会话"
        assert "天气" in results[0]["name"]

    def test_search_empty_conversation(self, service, login_account, test_app, db):
        """测试搜索没有消息的会话"""
        # 创建会话（没有消息）
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="未命名对话",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.commit()

        # 搜索"对话"
        results = service.search_conversations(login_account, "对话", limit=10)

        # 验证结果
        assert len(results) > 0, "应该找到会话名称包含'对话'的会话，即使没有消息"
        assert results[0]["name"] == "未命名对话"
        assert results[0]["matched_query"] == ""
        assert results[0]["matched_answer"] == ""

    def test_search_no_results(self, service, login_account, test_app, db):
        """测试搜索无结果"""
        # 创建会话和消息
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="测试会话",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            app_id=test_app.id,
            created_by=login_account.id,
            query="你好",
            answer="你好，我是助手",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 搜索不存在的内容
        results = service.search_conversations(login_account, "不存在的内容xyz", limit=10)

        # 验证结果
        assert len(results) == 0, "搜索不存在的内容应该返回空"

    def test_search_empty_query_returns_recent(self, service, login_account, test_app, db):
        """测试空搜索返回最近会话"""
        # 创建会话和消息
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="最近的对话",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            app_id=test_app.id,
            created_by=login_account.id,
            query="你好",
            answer="你好，我是助手",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)

        # 设置 assistant_agent_conversation_id
        login_account.assistant_agent_conversation_id = conversation.id
        db.session.commit()

        # 空搜索
        results = service.search_conversations(login_account, "", limit=10)

        # 验证结果
        assert len(results) > 0, "空搜索应该返回最近会话"
        assert results[0]["name"] == "最近的对话"

    def test_search_limit_validation(self, service, login_account, test_app, db):
        """测试搜索结果数量限制"""
        # 创建多个会话和消息
        for i in range(5):
            conversation = Conversation(
                id=uuid4(),
                created_by=login_account.id,
                name=f"测试会话{i}",
                invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
                app_id=test_app.id,
            )
            db.session.add(conversation)
            db.session.flush()

            message = Message(
                id=uuid4(),
                conversation_id=conversation.id,
                app_id=test_app.id,
                created_by=login_account.id,
                query="测试内容",
                answer="测试答案",
                status=MessageStatus.NORMAL.value,
                invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            )
            db.session.add(message)
        db.session.commit()

        # 搜索"测试"，限制为2条
        results = service.search_conversations(login_account, "测试", limit=2)

        # 验证结果
        assert len(results) <= 2, "搜索结果应该不超过limit"

    def test_search_only_own_conversations(self, service, login_account, test_app, db):
        """测试只能搜索自己的会话"""
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
            icon="default_icon",
            description="其他应用描述",
            status="draft",
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
            app_id=other_app.id,
            created_by=other_account.id,
            query="其他用户的查询",
            answer="其他用户的答案",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(other_message)
        db.session.commit()

        # 当前用户搜索"其他用户"
        results = service.search_conversations(login_account, "其他用户", limit=10)

        # 验证结果
        assert len(results) == 0, "不应该搜索到其他用户的会话"

    def test_search_result_format(self, service, login_account, test_app, db):
        """测试搜索结果格式正确"""
        # 创建会话和消息
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="格式测试",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            app_id=test_app.id,
            created_by=login_account.id,
            query="测试查询",
            answer="测试答案",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 搜索
        results = service.search_conversations(login_account, "测试", limit=10)

        # 验证结果格式
        assert len(results) > 0
        result = results[0]

        # 检查必需字段
        assert "id" in result
        assert "name" in result
        assert "source_type" in result
        assert "app_id" in result
        assert "app_name" in result
        assert "matched_query" in result
        assert "matched_answer" in result
        assert "latest_message_at" in result
        assert "created_at" in result

        # 检查字段类型
        assert isinstance(result["id"], str), "id应该是字符串"
        assert isinstance(result["name"], str), "name应该是字符串"
        assert isinstance(result["source_type"], str), "source_type应该是字符串"
        assert isinstance(result["app_id"], str), "app_id应该是字符串"
        assert isinstance(result["latest_message_at"], int), "latest_message_at应该是整数"
        assert isinstance(result["created_at"], int), "created_at应该是整数"

    def test_search_long_message_truncation(self, service, login_account, test_app, db):
        """测试长消息截取"""
        # 创建会话
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="长消息测试",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        # 创建长消息
        long_query = "这是一个很长的查询" * 50  # 超过200字符
        long_answer = "这是一个很长的答案" * 50  # 超过200字符

        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            app_id=test_app.id,
            created_by=login_account.id,
            query=long_query,
            answer=long_answer,
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 搜索
        results = service.search_conversations(login_account, "很长", limit=10)

        # 验证结果
        assert len(results) > 0
        result = results[0]

        # 检查截取
        assert len(result["matched_query"]) <= 300, "matched_query应该被截取"
        assert len(result["matched_answer"]) <= 300, "matched_answer应该被截取"

    def test_search_case_insensitive(self, service, login_account, test_app, db):
        """测试搜索不区分大小写"""
        # 创建会话
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="Python教程",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            app_id=test_app.id,
            created_by=login_account.id,
            query="Learn Python",
            answer="Python is great",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 搜索"python"（小写）
        results = service.search_conversations(login_account, "python", limit=10)

        # 验证结果
        assert len(results) > 0, "搜索应该不区分大小写"

    def test_search_multiple_matches_in_same_conversation(self, service, login_account, test_app, db):
        """测试同一会话中多条消息匹配"""
        # 创建会话
        conversation = Conversation(
            id=uuid4(),
            created_by=login_account.id,
            name="多消息会话",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        # 创建多条消息
        for i in range(3):
            message = Message(
                id=uuid4(),
                conversation_id=conversation.id,
                app_id=test_app.id,
                created_by=login_account.id,
                query=f"天气查询{i}",
                answer=f"天气答案{i}",
                status=MessageStatus.NORMAL.value,
                invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            )
            db.session.add(message)
        db.session.commit()

        # 搜索"天气"
        results = service.search_conversations(login_account, "天气", limit=10)

        # 验证结果
        assert len(results) > 0, "应该找到包含'天气'的消息"
        # 同一会话只应该返回一条结果
        assert results[0]["name"] == "多消息会话"


# 修复：test_search_empty_query_returns_recent 需要设置 assistant_agent_conversation_id
# 这是一个已知的问题，在 get_recent_conversations 中会检查这个属性
