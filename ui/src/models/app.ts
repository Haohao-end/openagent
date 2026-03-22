import {
  type BasePaginatorRequest,
  type BasePaginatorResponse,
  type BaseResponse,
} from '@/models/base' // 获取应用信息响应结构

// 应用版本类型
export type AppVersion = {
  id: string
  app_id: string
  version: number
  config: Record<string, any>
  created_at: number
  updated_at: number
}

// 获取应用信息响应结构
export type GetAppResponse = BaseResponse<{
  id: string
  debug_conversation_id: string
  name: string
  icon: string
  description: string
  status: string
  is_public: boolean
  category: string
  draft_updated_at: number
  updated_at: number
  created_at: number
}>

// 新增应用请求结构
export type CreateAppRequest = { name: string; icon: string; description: string }

// 更新应用请求结构
export type UpdateAppRequest = { name: string; icon: string; description: string }

// 获取应用分页列表数据请求
export type GetAppsWithPageRequest = BasePaginatorRequest & { search_word: string }

// 获取应用分页列表数据响应
export type GetAppsWithPageResponse = BasePaginatorResponse<{
  id: string
  name: string
  icon: string
  description: string
  preset_prompt: string
  model_config: {
    provider: string
    model: string
  }
  status: string
  creator_name: string
  creator_avatar: string
  draft_updated_at: number
  updated_at: number
  created_at: number
}>

// 获取特定应用的草稿配置响应结构
export type GetDraftAppConfigResponse = BaseResponse<{
  id: string
  model_config: { provider: string; model: string; parameters: Record<string, any> }
  dialog_round: number
  preset_prompt: string
  tools: {
    type: string
    provider: { id: string; name: string; label: string; icon: string; description: string }
    tool: {
      id: string
      name: string
      label: string
      description: string
      params: Record<string, any>
    }
  }[]
  workflows: { id: string; name: string; icon: string; description: string }[]
  datasets: { id: string; name: string; icon: string; description: string }[]
  retrieval_config: { retrieval_strategy: string; k: number; score: number }
  long_term_memory: { enable: boolean }
  opening_statement: string
  opening_questions: string[]
  speech_to_text: { enable: boolean }
  text_to_speech: { enable: boolean; voice: string; auto_play: boolean }
  suggested_after_answer: { enable: boolean }
  review_config: {
    enable: boolean
    keywords: string[]
    inputs_config: { enable: boolean; preset_response: string }
    outputs_config: { enable: boolean }
  }
  updated_at: number
  created_at: number
}>

// 更新特定应用的草稿配置请求结构
export type UpdateDraftAppConfigRequest = {
  model_config?: { provider: string; model: string; parameters: Record<string, any> }
  dialog_round?: number
  preset_prompt?: string
  tools?: { type: string; provider_id: string; tool_id: string; params: Record<string, any> }[]
  workflows?: string[]
  datasets?: string[]
  retrieval_config?: { retrieval_strategy: string; k: number; score: number }
  long_term_memory?: { enable: boolean }
  opening_statement?: string
  opening_questions?: string[]
  speech_to_text?: { enable: boolean }
  text_to_speech?: { enable: boolean; voice: string; auto_play: boolean }
  suggested_after_answer?: { enable: boolean }
  review_config?: {
    enable: boolean
    keywords: string[]
    inputs_config: { enable: boolean; preset_response: string }
    outputs_config: { enable: boolean }
  }
}

// 获取应用的调试会话消息列表响应结构
export type GetDebugConversationMessagesWithPageResponse = BasePaginatorResponse<{
  id: string
  conversation_id: string
  query: string
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

// 获取应用的发布历史配置列表分页响应结构
export type GetPublishHistoriesWithPageResponse = BasePaginatorResponse<{
  id: string
  version: number
  created_at: number
}>

// 获取应用的调试会话消息列表请求结构
export type GetDebugConversationMessagesWithPageRequest = BasePaginatorRequest & {
  created_at?: number
  conversation_id?: string
}

// 获取应用发布配置响应结构
export type GetPublishedConfigResponse = BaseResponse<{
  web_app: {
    token: string
    status: string
  }
}>

// 重新生成WebApp凭证标识响应结构
export type RegenerateWebAppTokenResponse = BaseResponse<{
  token: string
}>
