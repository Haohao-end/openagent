import { get } from '@/utils/request'
import type { BaseResponse } from '@/models/base'
import type { SpaceResourceCardItem, SpaceResourceType } from '@/models/space-resource'

export type GetFavoritesParams = {
  search_word?: string
  resource_type?: SpaceResourceType | 'all'
}

export function getFavorites(params: GetFavoritesParams = {}) {
  return get<BaseResponse<SpaceResourceCardItem[]>>('/favorites', { params })
}
