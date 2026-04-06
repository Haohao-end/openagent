from dataclasses import dataclass
from uuid import UUID
from flask import request
from flask_login import login_required, current_user
from injector import inject
from internal.schema.conversation_schema import (
    GetConversationMessagesWithPageReq,
    GetConversationMessagesWithPageResp,
    GetRecentConversationsReq,
    GetRecentConversationsResp,
    UpdateConversationNameReq,
    UpdateConversationIsPinnedReq,
    SearchConversationsReq,
    SearchConversationsResp,
)
from internal.service import ConversationService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_json, success_message



@inject
@dataclass
class ConversationHandler:
    """会话处理器"""
    conversation_service: ConversationService

    @login_required
    def get_conversation_messages_with_page(self, conversation_id: UUID):
        """根据传递的会话id获取该会话的消息列表分页数据"""
        # 1.提取数据并校验
        req = GetConversationMessagesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务获取消息列表
        messages, paginator = self.conversation_service.get_conversation_messages_with_page(
            conversation_id,
            req,
            current_user
        )

        # 3.构建响应结构并返回
        resp = GetConversationMessagesWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(messages), paginator=paginator))

    @login_required
    def get_recent_conversations(self):
        """获取当前账号最近会话列表"""
        # 1.提取请求并校验数据
        req = GetRecentConversationsReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务获取数据
        conversations = self.conversation_service.get_recent_conversations(
            current_user,
            req.limit.data or 20,
        )

        # 3.构建响应结构并返回
        resp = GetRecentConversationsResp(many=True)
        return success_json(resp.dump(conversations))

    @login_required
    def delete_conversation(self, conversation_id: UUID):
        """根据传递的会话id删除指定的会话"""
        self.conversation_service.delete_conversation(conversation_id, current_user)

        return success_message("删除会话成功")

    @login_required
    def delete_message(self, conversation_id: UUID, message_id: UUID):
        """根据传递的会话id+消息id删除指定的消息"""
        self.conversation_service.delete_message(conversation_id, message_id, current_user)

        return success_message("删除会话消息成功")

    @login_required
    def get_conversation_name(self, conversation_id: UUID):
        """根据传递的会话id获取指定会话的名字"""
        # 1.调用服务获取会话
        conversation = self.conversation_service.get_conversation(conversation_id, current_user)

        # 2.构建响应结构并返回
        return success_json({"name": conversation.name})

    @login_required
    def update_conversation_name(self, conversation_id: UUID):
        """根据传递的会话id+name更新会话名字"""
        # 1.提取请求并校验
        req = UpdateConversationNameReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务更新会话名字
        self.conversation_service.update_conversation(conversation_id, current_user, name=req.name.data)

        return success_message("修改会话名称成功")

    @login_required
    def update_conversation_is_pinned(self, conversation_id: UUID):
        """根据传递的会话id+is_pinned更新会话的置顶状态"""
        # 1.提取请求并校验
        req = UpdateConversationIsPinnedReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务更新会话置顶状态
        self.conversation_service.update_conversation(conversation_id, current_user, is_pinned=req.is_pinned.data)

        return success_message("修改会话置顶状态成功")

    @login_required
    def search_conversations(self):
        """搜索会话及其消息内容"""
        # 1.提取请求并校验
        req = SearchConversationsReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务搜索会话
        conversations = self.conversation_service.search_conversations(
            current_user,
            req.query.data or "",
            req.limit.data or 50,
        )

        # 3.构建响应结构并返回
        resp = SearchConversationsResp(many=True)
        return success_json(resp.dump(conversations))
