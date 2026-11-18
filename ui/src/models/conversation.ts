import { type BasePaginatorRequest, type BasePaginatorResponse, type BaseResponse } from '@/models/base'

// 获取指定会话消息列表请求结构
export type GetConversationMessagesWithPageRequest = BasePaginatorRequest & {
  created_at: number
}

// 获取指定会话消息列表响应结构
export type GetConversationMessagesWithPageResponse = BasePaginatorResponse<{
  id: string
  conversation_id: string
  query: string
  image_urls: string[]
  input_parts: Array<Record<string, any>>
  answer: string
  answer_parts: Array<Record<string, any>>
  artifacts: Array<Record<string, any>>
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

export type RecentConversation = {
  id: string
  name: string
  source_type: 'assistant_agent' | 'app_debugger' | 'public_app'
  app_id: string
  app_name: string
  agent_name: string
  message_id: string
  is_active: boolean
  latest_message_at: number
  created_at: number
  human_message: string
  ai_message: string
}

export type GetRecentConversationsResponse = BaseResponse<RecentConversation[]>

export type MessageTraceSpan = {
  id: string
  position: number
  event: string
  thought: string
  observation: string
  tool: string
  tool_input: Record<string, any>
  latency: number
  total_token_count: number
  total_price: number
  created_at: number
}

export type MessageTraceData = {
  message_id: string
  conversation_id: string
  app_id: string
  status: string
  error: string
  latency: number
  total_token_count: number
  total_price: number
  created_at: number
  timeline: MessageTraceSpan[]
}

export type GetMessageTraceResponse = BaseResponse<MessageTraceData>
