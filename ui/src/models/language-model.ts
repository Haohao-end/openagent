import { type BaseResponse } from '@/models/base'

// 获取所有语言模型列表响应结构
export type GetLanguageModelsResponse = BaseResponse<
  {
    name: string
    position: number
    label: string
    icon: string
    description: string
    background: string
    support_model_types: string[]
    models: {
      model_name: string
      label: string
      model_type: string
      features: string[]
      context_windows: number
      max_output_tokens: number
      attributes: Record<string, any>
      metadata: Record<string, any>
      parameters: {
        name: string
        label: string
        type: string
        help: string
        required: boolean
        default: any
        min: number
        max: number
        precision: number
        options: {
          label: string
          value: any
        }[]
      }[]
    }[]
  }[]
>

// 获取指定语言模型详情响应结构
export type GetLanguageModelResponse = BaseResponse<{
  model: string
  label: string
  model_type: string
  features: string[]
  context_windows: number
  max_output_tokens: number
  attributes: Record<string, any>
  metadata: Record<string, any>
  parameters: {
    name: string
    label: string
    type: string
    help: string
    required: boolean
    default: any
    min: number
    max: number
    precision: number
    options: {
      label: string
      value: any
    }[]
  }[]
}>
