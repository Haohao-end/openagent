import { get } from '@/utils/request'
import type { BaseResponse } from '@/models/base'

export interface Tag {
  id: string
  name: string
  dimension: string
  use_count?: number
}

export interface AppTags {
  scene?: string[]
  ability?: string[]
  tech?: string[]
  industry?: string[]
  [dimension: string]: string[] | undefined
}

export interface TagDimension {
  value: string
  label: string
}

export interface GetHotTagsResponse {
  hot_tags: Record<string, Tag[]>
}

export interface GetTagDimensionsResponse {
  dimensions: TagDimension[]
}

export function getHotTags() {
  return get<BaseResponse<GetHotTagsResponse>>('/tags/hot')
}

export function getTagDimensions() {
  return get<BaseResponse<GetTagDimensionsResponse>>('/tags/dimensions')
}
