import type { BaseResponse } from '@/models/base'

// 获取微信配置响应结构
export type GetWechatConfigResponse = BaseResponse<{
  app_id: string
  ip: string
  url: string
  wechat_app_id: string
  wechat_app_secret: string
  wechat_app_token: string
  status: string
  updated_at: number
  created_at: number
}>

// 更新微信配置请求结构
export type UpdateWechatConfigRequest = {
  wechat_app_id?: string
  wechat_app_secret?: string
  wechat_token?: string
}