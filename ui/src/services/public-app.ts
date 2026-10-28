/**
 * 公共应用广场API服务
 */
import { get, post, ssePost } from '@/utils/request'
import type { BaseResponse, BasePaginatorResponse } from '@/models/base'

export interface PublicApp {
  id: string
  name: string
  icon: string
  description: string
  tags: string[]
  creator_name: string  // 发布者名称
  creator_avatar: string  // 发布者头像
  published_at: number
  created_at: number
  updated_at?: number
  is_forked?: boolean  // 是否已fork
  status?: string
  is_public?: boolean
  draft_app_config?: Record<string, unknown>  // 应用配置信息
}

export interface AppTag {
  id: string
  name: string
  priority: number
}

export interface GetPublicAppsParams {
  current_page?: number
  page_size?: number
  tags?: string
  search_word?: string
}

/**
 * 获取公共应用列表
 */
export function getPublicApps(params: GetPublicAppsParams) {
  return get<BasePaginatorResponse<PublicApp>>('/public/apps', { params })
}

/**
 * 获取应用标签列表
 */
export function getAppTags() {
  return get<BaseResponse<{ tags: AppTag[] }>>('/public/apps/tags')
}

/**
 * 共享应用到广场
 */
export function shareAppToSquare(appId: string, tags: string) {
  return post<BaseResponse<any>>(`/apps/${appId}/share-to-square`, { body: { tags } })
}

/**
 * 取消共享应用
 */
export function unshareAppFromSquare(appId: string) {
  return post<BaseResponse<any>>(`/apps/${appId}/unshare-from-square`)
}

/**
 * Fork应用到个人空间
 */
export function forkPublicApp(appId: string) {
  return post<BaseResponse<{ id: string; name: string }>>(`/public/apps/${appId}/fork`)
}

/**
 * 获取公共应用详情
 */
export function getPublicAppDetail(appId: string) {
  return get<BaseResponse<PublicApp>>(`/public/apps/${appId}`)
}

/**
 * 通过公开A2A接口向应用发送消息
 */
export function sendPublicAppA2aMessage(
  appId: string,
  message: string,
  contextId: string = '',
  imageUrls: string[] = [],
  onData?: Parameters<typeof ssePost>[2],
) {
  const req = {
    message: {
      role: 'user',
      parts: [
        { type: 'text', text: message },
        ...imageUrls.map((url) => ({ type: 'image', url })),
      ],
    },
    contextId,
  }
  if (onData) {
    return ssePost(`/public/apps/${appId}/a2a/messages`, { body: req }, onData)
  }
  return post<BaseResponse<{
    contextId: string
    message: {
      role: string
      parts: Array<Record<string, unknown>>
    }
    artifacts: unknown[]
    metadata: Record<string, unknown>
  }>>(`/public/apps/${appId}/a2a/messages`, { body: req })
}

export function getPublicAppA2aConversationMessages(appId: string, conversationId: string) {
  return get<BaseResponse<Array<{
    id: string
    conversation_id: string
    query: string
    image_urls: string[]
    input_parts: Array<Record<string, unknown>>
    answer: string
    answer_parts: Array<Record<string, unknown>>
    artifacts: Array<Record<string, unknown>>
    total_token_count: number
    latency: number
    suggested_questions: string[]
  }>>>(`/public/apps/${appId}/a2a/conversations/${conversationId}/messages`)
}
