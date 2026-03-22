#!/usr/bin/env python3
"""
清理测试对话数据脚本
"""
import sys
sys.path.insert(0, '/home/haohao/llmops/api')

from app.http.app import app
from pkg.sqlalchemy import SQLAlchemy
from internal.model import Conversation

# 获取数据库实例
db = app.extensions.get('sqlalchemy')

with app.app_context():
    # 查询包含测试关键词的对话
    test_conversations = Conversation.query.filter(
        Conversation.name.in_(['测试对话1', '测试对话2', '测试对话3'])
    ).all()

    print(f"找到 {len(test_conversations)} 个测试对话")

    for conv in test_conversations:
        print(f"删除: {conv.name} (ID: {conv.id})")
        db.session.delete(conv)

    # 提交删除
    db.session.commit()
    print("✅ 测试对话已全部删除")
