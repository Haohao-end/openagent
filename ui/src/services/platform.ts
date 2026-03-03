import { get, post } from '@/utils/request'
import type { GetWechatConfigResponse, UpdateWechatConfigRequest } from '@/models/platform'
import type { BaseResponse } from '@/models/base'


// 获取指定 Agent 的微信公众号发布配置信息
export const getWechatConfig = (app_id: string) => {
  return get<GetWechatConfigResponse>(`/platform/${app_id}/wechat-config`)
}

// 更新指定 Agent 的微信公众号发布配置
export const updateWechatConfig = (app_id: string, req: UpdateWechatConfigRequest) => {
  return post<BaseResponse<any>>(`/platform/${app_id}/wechat-config`, { body: req })
}