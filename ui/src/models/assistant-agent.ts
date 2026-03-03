import type { BasePaginatorRequest, BasePaginatorResponse, BaseResponse } from '@/models/base'

// 获取辅助Agent会话消息分页列表请求结构
export type GetAssistantAgentMessagesWithPageRequest = BasePaginatorRequest & {
  created_at?: number
  conversation_id?: string
}

// 获取辅助Agent会话消息分页列表响应结构
export type GetAssistantAgentMessagesWithPageResponse = BasePaginatorResponse<{
  id: string
  conversation_id: string
  query: string
  image_urls: string[]
  answer: string
  total_token_count: number
  latency: number
  agent_thoughts: {
    id: string
    position: number
    event: string
    thought: string
    observation: string
    tool: string
    tool_input: Record<string, any>
    latency: number
    created_at: number
  }[]
  suggested_questions: string[]
  created_at: number
}>

export type AssistantAgentConversation = {
  id: string
  name: string
  is_active: boolean
  updated_at: number
  created_at: number
}

export type GetAssistantAgentConversationsResponse = BaseResponse<AssistantAgentConversation[]>
