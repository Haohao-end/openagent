import { get } from '@/utils/request'
import type { BaseResponse } from '@/models/base'
import type { SpaceResourceCardItem, SpaceResourceType } from '@/models/space-resource'

export type GetLikesParams = {
  search_word?: string
  resource_type?: SpaceResourceType | 'all'
}

export function getLikes(params: GetLikesParams = {}) {
  return get<BaseResponse<SpaceResourceCardItem[]>>('/likes', { params })
}
