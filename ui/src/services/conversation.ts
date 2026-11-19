import { get, post } from '@/utils/request'
import type {
  CompareMessagesRequest,
  CompareMessagesResponse,
  GetConversationMessagesWithPageRequest,
  GetConversationMessagesWithPageResponse,
  GetMessageTraceResponse,
  GetRecentConversationsResponse,
  ReplayMessageRequest,
  ReplayMessageResponse,
} from '@/models/conversation'
import type { BaseResponse } from '@/models/base'

// 获取指定会话的消息列表
export const getConversationMessages = (
  conversation_id: string,
  req: GetConversationMessagesWithPageRequest,
) => {
  return get<GetConversationMessagesWithPageResponse>(
    `/conversations/${conversation_id}/messages`,
    { params: req },
  )
}

// 删除特定的会话
export const deleteConversation = (conversation_id: string) => {
  return post<BaseResponse<any>>(`/conversations/${conversation_id}/delete`)
}

// 删除特定会话下的指定消息
export const deleteMessage = (conversation_id: string, message_id: string) => {
  return post<BaseResponse<any>>(`/conversations/${conversation_id}/messages/${message_id}/delete`)
}

// 获取指定会话的名称
export const getConversationName = (conversation_id: string) => {
  return get<BaseResponse<{ name: string }>>(`/conversations/${conversation_id}/name`)
}

// 修改指定会话的名称
export const updateConversationName = (conversation_id: string, name: string) => {
  return post<BaseResponse<any>>(`/conversations/${conversation_id}/name`, { body: { name } })
}

// 置顶或取消置顶某个会话
export const updateConversationIsPinned = (conversation_id: string, is_pinned: boolean) => {
  return post<BaseResponse<any>>(`/conversations/${conversation_id}/is-pinned`, {
    body: { is_pinned },
  })
}

// 获取最近会话列表（主页助手+应用调试）
export const getRecentConversations = (limit: number = 20) => {
  return get<GetRecentConversationsResponse>(`/conversations/recent`, {
    params: { limit },
  })
}

// 获取消息执行 Trace 时间线详情
export const getMessageTrace = (message_id: string) => {
  return get<GetMessageTraceResponse>(`/conversations/messages/${message_id}/trace`)
}

// 比较两次运行消息差异
export const compareMessages = (req: CompareMessagesRequest) => {
  return post<CompareMessagesResponse>(`/conversations/messages/compare`, { body: req })
}

// 重放运行消息并应用 Patch 配置
export const replayMessage = (message_id: string, req?: ReplayMessageRequest) => {
  return post<ReplayMessageResponse>(`/conversations/messages/${message_id}/replay`, {
    body: req ?? {},
  })
}
