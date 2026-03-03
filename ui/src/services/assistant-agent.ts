import { get, post, ssePost } from '@/utils/request'
import type { BaseResponse } from '@/models/base'
import type {
  GetAssistantAgentConversationsResponse,
  GetAssistantAgentMessagesWithPageRequest,
  GetAssistantAgentMessagesWithPageResponse,
} from '@/models/assistant-agent'

// 与辅助Agent进行对话
export const assistantAgentChat = (
  query: string,
  image_urls: string[] = [],
  conversation_id: string = '',
  onData: (event_response: Record<string, any>) => void,
) => {
  return ssePost(`/assistant-agent/chat`, { body: { query, image_urls, conversation_id } }, onData)
}

// 生成辅助Agent首页个性化介绍
export const assistantAgentGenerateIntroduction = (
  onData: (event_response: Record<string, any>) => void,
  signal?: AbortSignal,
) => {
  return ssePost(`/assistant-agent/introduction`, { body: {}, signal }, onData)
}

// 停止与辅助Agent进行对话
export const stopAssistantAgentChat = (task_id: string) => {
  return post<BaseResponse<any>>(`/assistant-agent/chat/${task_id}/stop`)
}

// 获取当前登录账号的辅助 Agent 对话历史列表
export const getAssistantAgentMessagesWithPage = (
  req?: GetAssistantAgentMessagesWithPageRequest,
) => {
  return get<GetAssistantAgentMessagesWithPageResponse>(`/assistant-agent/messages`, {
    params: req,
  })
}

// 获取当前登录账号的辅助 Agent 最近会话列表
export const getAssistantAgentConversations = (limit: number = 20) => {
  return get<GetAssistantAgentConversationsResponse>(`/assistant-agent/conversations`, {
    params: { limit },
  })
}

// 清空当前登录账号与辅助 Agent 的对话列表
export const deleteAssistantAgentConversation = () => {
  return post<BaseResponse<any>>(`/assistant-agent/delete-conversation`)
}
