/**
 * 公共工作流广场API服务
 */
import { get, post } from '@/utils/request'
import type { BaseResponse, BasePaginatorResponse } from '@/models/base'

export interface PublicWorkflow {
  id: string
  name: string
  icon: string
  description: string
  tags: string[]
  view_count: number
  like_count: number
  fork_count: number
  favorite_count: number  // 新增收藏数
  published_at: number
  created_at: number
  is_liked: boolean
  is_favorited: boolean
  is_forked?: boolean  // 是否已fork
  account_name: string  // 新增发布者名称
  account_avatar: string  // 新增发布者头像
}

export interface GetPublicWorkflowsParams {
  current_page?: number
  page_size?: number
  tags?: string
  sort_by?: 'latest' | 'popular' | 'most_liked' | 'most_forked' | 'most_favorited'
  search_word?: string
}

/**
 * 获取公共工作流列表
 */
export function getPublicWorkflows(params: GetPublicWorkflowsParams) {
  return get<BasePaginatorResponse<PublicWorkflow>>('/public/workflows', { params })
}

/**
 * 共享工作流到广场
 */
export function shareWorkflowToSquare(workflowId: string, tags: string) {
  return post<BaseResponse<any>>(`/workflows/${workflowId}/share-to-square`, { body: { tags } })
}

/**
 * 取消共享工作流
 */
export function unshareWorkflowFromSquare(workflowId: string) {
  return post<BaseResponse<any>>(`/workflows/${workflowId}/unshare-from-square`)
}

/**
 * Fork工作流到个人空间
 */
export function forkPublicWorkflow(workflowId: string) {
  return post<BaseResponse<{ id: string; name: string }>>(`/public/workflows/${workflowId}/fork`)
}

/**
 * 点赞/取消点赞工作流
 */
export function likeWorkflow(workflowId: string) {
  return post<BaseResponse<{ is_liked: boolean; like_count: number }>>(
    `/public/workflows/${workflowId}/like`,
  )
}

/**
 * 收藏/取消收藏工作流
 */
export function favoriteWorkflow(workflowId: string) {
  return post<BaseResponse<{ is_favorited: boolean; favorite_count?: number }>>(
    `/public/workflows/${workflowId}/favorite`,
  )
}

/**
 * 获取公共工作流详情
 */
export function getPublicWorkflowDetail(workflowId: string) {
  return get<BaseResponse<PublicWorkflow>>(`/public/workflows/${workflowId}`)
}

/**
 * 获取公共工作流的草稿图配置
 */
export function getPublicWorkflowDraftGraph(workflowId: string) {
  return get<BaseResponse<{ nodes: Array<Record<string, unknown>>; edges: Array<Record<string, unknown>> }>>(
    `/public/workflows/${workflowId}/draft-graph`,
  )
}
