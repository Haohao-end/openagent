#!/usr/bin/env python
"""
测试搜索功能修复的脚本
验证会话名称搜索是否正常工作
"""
import sys
sys.path.insert(0, '/home/haohao/llmops/api')

from uuid import uuid4
from datetime import UTC, datetime
from internal.model import Account, Conversation, Message, App
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.service.conversation_service import ConversationService
from pkg.sqlalchemy import SQLAlchemy
from flask import Flask
from flask_sqlalchemy import SQLAlchemy as FlaskSQLAlchemy

# 创建测试应用
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:llmops123456@localhost:5432/llmops'
db = FlaskSQLAlchemy(app)

def test_search_by_conversation_name():
    """测试按会话名称搜索"""
    print("=" * 60)
    print("测试：按会话名称搜索")
    print("=" * 60)

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
            icon="default_icon",  # 添加必需的icon字段
            description="测试应用描述",  # 添加必需的description字段
            status="draft",  # 添加必需的status字段
        )
        db.session.add(test_app)
        db.session.flush()

        # 创建会话，名称包含"Python"
        conversation = Conversation(
            id=uuid4(),
            created_by=account.id,
            name="Python编程教程",  # 会话名称包含搜索词
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        # 创建消息，但消息内容不包含"Python"
        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            app_id=test_app.id,  # 添加app_id
            created_by=account.id,
            query="如何开始学习编程",
            answer="首先需要选择一门编程语言",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 创建服务实例
        service = ConversationService(db=db)

        # 搜索"Python"
        results = service.search_conversations(account, "Python", limit=10)

        print(f"\n搜索词: 'Python'")
        print(f"找到的结果数: {len(results)}")

        if len(results) > 0:
            result = results[0]
            print(f"\n✅ 成功找到会话!")
            print(f"  会话ID: {result['id']}")
            print(f"  会话名称: {result['name']}")
            print(f"  匹配的查询: {result['matched_query']}")
            print(f"  匹配的答案: {result['matched_answer']}")
            return True
        else:
            print(f"\n❌ 未找到会话 - BUG未修复!")
            return False

def test_search_by_message_content():
    """测试按消息内容搜索"""
    print("\n" + "=" * 60)
    print("测试：按消息内容搜索")
    print("=" * 60)

    with app.app_context():
        # 创建测试账号
        account = Account(
            id=uuid4(),
            email="test2@example.com",
            name="Test User 2",
        )
        db.session.add(account)
        db.session.flush()

        # 创建测试应用
        test_app = App(
            id=uuid4(),
            account_id=account.id,
            name="测试应用2",
            icon="default_icon",
            description="测试应用2描述",
            status="draft",
        )
        db.session.add(test_app)
        db.session.flush()

        # 创建会话，名称不包含搜索词
        conversation = Conversation(
            id=uuid4(),
            created_by=account.id,
            name="编程学习",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=test_app.id,
        )
        db.session.add(conversation)
        db.session.flush()

        # 创建消息，消息内容包含"JavaScript"
        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            app_id=test_app.id,  # 添加app_id
            created_by=account.id,
            query="如何学习JavaScript",
            answer="JavaScript是一门很好的编程语言",
            status=MessageStatus.NORMAL.value,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 创建服务实例
        service = ConversationService(db=db)

        # 搜索"JavaScript"
        results = service.search_conversations(account, "JavaScript", limit=10)

        print(f"\n搜索词: 'JavaScript'")
        print(f"找到的结果数: {len(results)}")

        if len(results) > 0:
            result = results[0]
            print(f"\n✅ 成功找到会话!")
            print(f"  会话ID: {result['id']}")
            print(f"  会话名称: {result['name']}")
            print(f"  匹配的查询: {result['matched_query']}")
            print(f"  匹配的答案: {result['matched_answer']}")
            return True
        else:
            print(f"\n❌ 未找到会话 - 消息搜索失败!")
            return False

if __name__ == "__main__":
    try:
        test1_passed = test_search_by_conversation_name()
        test2_passed = test_search_by_message_content()

        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        print(f"会话名称搜索: {'✅ 通过' if test1_passed else '❌ 失败'}")
        print(f"消息内容搜索: {'✅ 通过' if test2_passed else '❌ 失败'}")

        if test1_passed and test2_passed:
            print("\n🎉 所有测试通过！搜索功能已修复！")
            sys.exit(0)
        else:
            print("\n⚠️  部分测试失败")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
