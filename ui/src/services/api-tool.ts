import { get, post } from '@/utils/request'
import {
  type CreateApiToolProviderRequest,
  type GetApiToolProviderResponse,
  type GetApiToolProvidersWithPageResponse,
  type GetApiToolResponse,
  type UpdateApiToolProviderRequest,
} from '@/models/api-tool'
import { type BaseResponse } from '@/models/base'

// 获取自定义API列表分页数据
export const getApiToolProvidersWithPage = (
  current_page: number = 1,
  page_size: number = 20,
  search_word: string = '',
) => {
  return get<GetApiToolProvidersWithPageResponse>('/api-tools', {
    params: { current_page, page_size, search_word },
  })
}

// 校验OpenAPI Schema数据
export const validateOpenAPISchema = (openapi_schema: string) => {
  return post<BaseResponse<any>>('/api-tools/validate-openapi-schema', {
    body: { openapi_schema },
  })
}

// 创建API工具提供者
export const createApiToolProvider = (req: CreateApiToolProviderRequest) => {
  return post<BaseResponse<any>>('/api-tools', {
    body: req,
  })
}

// 更新API工具提供者详情
export const updateApiToolProvider = (provider_id: string, req: UpdateApiToolProviderRequest) => {
  return post<BaseResponse<any>>(`/api-tools/${provider_id}`, {
    body: req,
  })
}

// 删除API工具提供者详情
export const deleteApiToolProvider = (provider_id: string) => {
  return post<BaseResponse<any>>(`/api-tools/${provider_id}/delete`)
}

// 获取API工具提供者详情
export const getApiToolProvider = (provider_id: string) => {
  return get<GetApiToolProviderResponse>(`/api-tools/${provider_id}`)
}

// 获取API工具详情信息
export const getApiTool = (provider_id: string, tool_name: string) => {
  return get<GetApiToolResponse>(`/api-tools/${provider_id}/tools/${tool_name}`)
}

// 重新生成插件图标
export const regenerateIcon = (provider_id: string) => {
  return post<BaseResponse<{ icon: string }>>(`/api-tools/${provider_id}/regenerate-icon`)
}

// 生成插件图标预览（不保存到插件）
export const generateIconPreview = (name: string, description: string) => {
  return post<BaseResponse<{ icon: string }>>(`/api-tools/generate-icon-preview`, {
    body: { name, description },
  })
}
