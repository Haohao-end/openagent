#!/usr/bin/env python
"""
完整的搜索功能测试 - 模拟真实的前端请求
"""
import sys
sys.path.insert(0, '/home/haohao/llmops/api')

from uuid import uuid4
from flask import Flask
from flask_sqlalchemy import SQLAlchemy as FlaskSQLAlchemy
from flask_login import LoginManager, UserMixin
from internal.model import Account, Conversation, Message, App
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.service.conversation_service import ConversationService
from internal.handler.conversation_handler import ConversationHandler
from internal.schema.conversation_schema import SearchConversationsResp
import json

# 创建测试应用
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:llmops123456@localhost:5432/llmops'
app.config['SECRET_KEY'] = 'test-secret-key'
db = FlaskSQLAlchemy(app)

# 设置登录管理
login_manager = LoginManager()
login_manager.init_app(app)

class TestUser(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

@login_manager.user_loader
def load_user(user_id):
    return TestUser(user_id)

def test_search_api_response():
    """测试搜索API的完整响应"""
    print("=" * 80)
    print("测试：搜索API完整响应")
    print("=" * 80)

    with app.app_context():
        # 创建测试账号
        account = Account(
            id=uuid4(),
            email="test@example.com",
            name="Test User",
        )
        db.session.add(account)
        db.session.flush()

        # 创建测试应用
        test_app = App(
            id=uuid4(),
            account_id=account.id,
            name="测试应用",
            icon="default_icon",
            description="测试应用描述",
            status="draft",
        )
        db.session.add(test_app)
        db.session.flush()

        # 创建会话1 - 通过名称匹配
        conversation1 = Conversation(
            id=uuid4(),
            created_by=account.id,
            name="Python编程教程",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation1)
        db.session.flush()

        message1 = Message(
            id=uuid4(),
            conversation_id=conversation1.id,
            app_id=test_app.id,
            created_by=account.id,
            query="如何开始学习编程",
            answer="首先需要选择一门编程语言",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message1)
        db.session.flush()

        # 创建会话2 - 通过消息内容匹配
        conversation2 = Conversation(
            id=uuid4(),
            created_by=account.id,
            name="编程学习",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation2)
        db.session.flush()

        message2 = Message(
            id=uuid4(),
            conversation_id=conversation2.id,
            app_id=test_app.id,
            created_by=account.id,
            query="如何学习JavaScript",
            answer="JavaScript是一门很好的编程语言",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message2)
        db.session.commit()

        # 创建服务实例
        service = ConversationService(db=db)

        # 测试1：搜索"Python"
        print("\n【测试1】搜索词: 'Python'")
        results = service.search_conversations(account, "Python", limit=10)
        print(f"后端返回结果数: {len(results)}")

        if len(results) > 0:
            result = results[0]
            print(f"✅ 找到结果")
            print(f"  - id 类型: {type(result['id']).__name__} = {result['id']}")
            print(f"  - name: {result['name']}")
            print(f"  - app_id 类型: {type(result['app_id']).__name__} = {result['app_id']}")
            print(f"  - matched_query: {result['matched_query']}")
            print(f"  - matched_answer: {result['matched_answer']}")

            # 测试Schema序列化
            print("\n  【Schema序列化测试】")
            resp_schema = SearchConversationsResp(many=True)
            try:
                serialized = resp_schema.dump(results)
                print(f"  ✅ Schema序列化成功")
                print(f"  序列化后的数据: {json.dumps(serialized, indent=2, default=str)}")
            except Exception as e:
                print(f"  ❌ Schema序列化失败: {str(e)}")
                import traceback
                traceback.print_exc()
        else:
            print(f"❌ 未找到结果")

        # 测试2：搜索"JavaScript"
        print("\n【测试2】搜索词: 'JavaScript'")
        results = service.search_conversations(account, "JavaScript", limit=10)
        print(f"后端返回结果数: {len(results)}")

        if len(results) > 0:
            result = results[0]
            print(f"✅ 找到结果")
            print(f"  - id: {result['id']}")
            print(f"  - name: {result['name']}")
            print(f"  - matched_query: {result['matched_query']}")
            print(f"  - matched_answer: {result['matched_answer']}")
        else:
            print(f"❌ 未找到结果")

        # 测试3：空搜索（应该返回最近会话）
        print("\n【测试3】空搜索词（应返回最近会话）")
        results = service.search_conversations(account, "", limit=10)
        print(f"后端返回结果数: {len(results)}")

        if len(results) > 0:
            print(f"✅ 找到最近会话")
            for i, result in enumerate(results):
                print(f"  [{i+1}] {result['name']}")
        else:
            print(f"❌ 未找到最近会话")

if __name__ == "__main__":
    try:
        test_search_api_response()
        print("\n" + "=" * 80)
        print("✅ 测试完成")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ 测试出错: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
