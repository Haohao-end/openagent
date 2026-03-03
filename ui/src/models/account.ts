import { type BaseResponse } from '@/models/base'

// 获取当前登录账号响应结构
export type GetCurrentUserResponse = BaseResponse<{
  id: string
  name: string
  email: string
  avatar: string
  last_login_ip: string
  last_login_at: number
  created_at: number
}>
