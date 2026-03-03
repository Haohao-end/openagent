import { type BaseResponse } from '@/models/base'

// 获取指定第三方授权服务重定向响应结构
export type ProviderResponse = BaseResponse<{
  redirect_url: string
}>

// 指定第三方授权认证登录响应结构
export type AuthorizeResponse = BaseResponse<{
  access_token: string
  expire_at: number
}>
