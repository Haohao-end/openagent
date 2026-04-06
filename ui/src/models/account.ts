import { type BaseResponse } from '@/models/base'

export type OAuthBindingItem = {
  provider: string
  bound: boolean
  bound_at: number
}

export type AccountSessionItem = {
  id: string
  current: boolean
  legacy: boolean
  device_name: string
  user_agent: string
  ip: string
  location: string
  created_at: number
  last_active_at: number
  expires_at: number
}

export type AccountLoginHistoryItem = {
  id: string
  current: boolean
  legacy: boolean
  device_name: string
  user_agent: string
  ip: string
  location: string
  status: 'active' | 'revoked' | 'expired' | 'legacy'
  unusual_ip: boolean
  created_at: number
  last_active_at: number
  expires_at: number
  revoked_at: number
}

// 获取当前登录账号响应结构
export type GetCurrentUserResponse = BaseResponse<{
  id: string
  name: string
  email: string
  avatar: string
  last_login_ip: string
  last_login_location: string
  last_login_at: number
  created_at: number
  password_set: boolean
  oauth_bindings: OAuthBindingItem[]
}>

export type GetAccountSessionsResponse = BaseResponse<{
  session_capable: boolean
  current_session_id: string | null
  sessions: AccountSessionItem[]
}>

export type GetAccountLoginHistoryResponse = BaseResponse<{
  history: AccountLoginHistoryItem[]
  total: number
  current_page: number
  page_size: number
}>
