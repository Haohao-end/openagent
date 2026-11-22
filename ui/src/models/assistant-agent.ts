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

export type AssistantAgentConversation = {
  id: string
  name: string
  is_active: boolean
  updated_at: number
  created_at: number
}

export type GetAssistantAgentConversationsResponse = BaseResponse<AssistantAgentConversation[]>

export type GetAssistantAgentCapabilitiesResponse = BaseResponse<{
  capabilities: {
    requested_model: { provider: string; model: string }
    effective_model: { provider: string; model: string }
    features: string[]
    requested_features: string[]
    image_input: {
      enabled: boolean
      via_fallback: boolean
      policy: string
      requested_model_supports: boolean
      effective_model_supports: boolean
      fallback_model: { provider: string; model: string } | null
      fallback_model_supports: boolean
      reason_code: string
      message: string
    }
    image_output: { enabled: boolean; reason_code: string }
    artifact_output: { enabled: boolean; reason_code: string }
  }
}>
