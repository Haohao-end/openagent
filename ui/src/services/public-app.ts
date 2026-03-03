/**
 * 公共应用广场API服务
 */
import { get, post } from '@/utils/request'
import type { BaseResponse, BasePaginatorResponse } from '@/models/base'

export interface PublicApp {
  id: string
  name: string
  icon: string
  description: string
  category: string
  view_count: number
  like_count: number
  fork_count: number
  favorite_count: number  // 收藏数
  creator_name: string  // 发布者名称
  published_at: number
  created_at: number
  updated_at?: number
  is_liked: boolean
  is_favorited: boolean
  status?: string
  is_public?: boolean
  draft_app_config?: Record<string, unknown>  // 应用配置信息
}

export interface AppCategory {
  value: string
  label: string
}

export interface GetPublicAppsParams {
  current_page?: number
  page_size?: number
  category?: string
  sort_by?: 'latest' | 'popular' | 'most_liked' | 'most_forked' | 'most_favorited'
  search_word?: string
}

/**
 * 获取公共应用列表
 */
export function getPublicApps(params: GetPublicAppsParams) {
  return get<BasePaginatorResponse<PublicApp>>('/public/apps', { params })
}

/**
 * 获取应用分类列表
 */
export function getAppCategories() {
  return get<BaseResponse<{ categories: AppCategory[] }>>('/public/apps/categories')
}

/**
 * 共享应用到广场
 */
export function shareAppToSquare(appId: string, category: string) {
  return post<BaseResponse<any>>(`/apps/${appId}/share-to-square`, { body: { category } })
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
 * 点赞/取消点赞应用
 */
export function likeApp(appId: string) {
  return post<BaseResponse<{ is_liked: boolean; like_count: number }>>(`/public/apps/${appId}/like`)
}

/**
 * 收藏/取消收藏应用
 */
export function favoriteApp(appId: string) {
  return post<BaseResponse<{ is_favorited: boolean; favorite_count?: number }>>(
    `/public/apps/${appId}/favorite`,
  )
}

/**
 * 获取我的收藏列表
 */
export function getMyFavorites() {
  return get<BaseResponse<PublicApp[]>>('/public/apps/my-favorites')
}

/**
 * 获取公共应用详情
 */
export function getPublicAppDetail(appId: string) {
  return get<BaseResponse<PublicApp>>(`/public/apps/${appId}`)
}

/**
 * 获取公共应用统计分析数据
 */
export function getPublicAppAnalysis(appId: string) {
  return get<BaseResponse<any>>(`/public/apps/${appId}/analysis`)
}
