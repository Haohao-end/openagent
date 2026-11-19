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

// 比较运行消息请求结构
export type CompareMessagesRequest = {
  target_message_id: string
  base_message_id: string
}

// 单次运行概览数据
export type MessageRunSummary = {
  id: string
  status: string
  error: string
  latency: number
  total_token_count: number
  total_price: number
  answer_length: number
}

// 两次运行差异指标
export type MessageRunDiff = {
  latency_diff: number
  total_token_count_diff: number
  message_token_count_diff: number
  answer_token_count_diff: number
  total_price_diff: number
  status_changed: boolean
  error_changed: boolean
  answer_match: boolean
  answer_length_diff: number
}

// 比较运行消息差异数据
export type CompareMessagesData = {
  target: MessageRunSummary
  base: MessageRunSummary
  diff: MessageRunDiff
}

export type CompareMessagesResponse = BaseResponse<CompareMessagesData>

// 重放运行消息请求
export type ReplayMessageRequest = {
  patch?: Record<string, any>
}

// 重放输入及配置快照
export type ReplaySnapshotData = {
  message_id: string
  conversation_id: string
  app_id: string
  input_snapshot: {
    query: string
    image_urls: string[]
  }
  config_snapshot: {
    model_config?: Record<string, any>
    preset_prompt?: string
    retrieval_config?: Record<string, any>
    tools?: Array<Record<string, any>>
    datasets?: Array<Record<string, any>>
    workflows?: Array<Record<string, any>>
  }
  patched_config: Record<string, any>
  applied_patch_keys: string[]
}

export type ReplayMessageResponse = BaseResponse<ReplaySnapshotData>
