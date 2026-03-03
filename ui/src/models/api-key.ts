import { type BasePaginatorResponse } from '@/models/base'

// 新增API秘钥请求
export type CreateApiKeyRequest = {
  is_active?: boolean
  remark?: string
}

export type CreateApiKeyResponse = {
  api_key: string
}

// 修改API秘钥请求
export type UpdateApiKeyRequest = {
  is_active?: boolean
  remark?: string
}

// 获取API秘钥列表响应数据
export type GetApiKeysWithPageResponse = BasePaginatorResponse<{
  id: string
  api_key: string
  is_active: boolean
  remark: string
  updated_at: number
  created_at: number
}>
