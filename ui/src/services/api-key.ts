import { get, post } from '@/utils/request'
import { type BasePaginatorRequest, type BaseResponse } from '@/models/base'
import {
  type CreateApiKeyRequest,
  type CreateApiKeyResponse,
  type GetApiKeysWithPageResponse,
  type UpdateApiKeyRequest,
} from '@/models/api-key'

// 创建API秘钥请求
export const createApiKey = (req: CreateApiKeyRequest) => {
  return post<BaseResponse<CreateApiKeyResponse>>(`/openapi/api-keys`, { body: req })
}

// 删除API秘钥请求
export const deleteApiKey = (api_key_id: string) => {
  return post<BaseResponse<any>>(`/openapi/api-keys/${api_key_id}/delete`)
}

// 修改API秘钥请求
export const updateApiKey = (api_key_id: string, req: UpdateApiKeyRequest) => {
  return post<BaseResponse<any>>(`/openapi/api-keys/${api_key_id}`, { body: req })
}

// 修改API秘钥激活请求
export const updateApiKeyIsActive = (api_key_id: string, is_active: boolean) => {
  return post<BaseResponse<any>>(`/openapi/api-keys/${api_key_id}/is-active`, {
    body: { is_active },
  })
}

// 获取API秘钥分页列表数据
export const getApiKeysWithPage = (req: BasePaginatorRequest) => {
  return get<GetApiKeysWithPageResponse>(`/openapi/api-keys`, { params: req })
}
