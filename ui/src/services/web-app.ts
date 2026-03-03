import { get, post, ssePost } from '@/utils/request'
import type {
  GetWebAppConversationsResponse,
  GetWebAppResponse,
  WebAppChatRequest,
} from '@/models/web-app'
import type { BaseResponse } from '@/models/base'

// 根据标识获取指定 WebApp 基础信息
export const getWebApp = (token: string) => {
  return get<GetWebAppResponse>(`/web-apps/${token}`)
}

// 与指定 WebApp 进行对话
export const webAppChat = (
  token: string,
  req: WebAppChatRequest,
  onData: (event_response: Record<string, any>) => void,
) => {
  return ssePost(`/web-apps/${token}/chat`, { body: req }, onData)
}

// 停止与指定 WebApp 进行对话
export const stopWebAppChat = (token: string, task_id: string) => {
  return post<BaseResponse<any>>(`/web-apps/${token}/chat/${task_id}/stop`)
}

// 获取指定应用的会话列表
export const getWebAppConversations = (token: string, is_pinned: boolean = false) => {
  return get<GetWebAppConversationsResponse>(`/web-apps/${token}/conversations`, {
    params: { is_pinned },
  })
}
