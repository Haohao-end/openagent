import {
  type BasePaginatorRequest,
  type BasePaginatorResponse,
  type BaseResponse,
} from '@/models/base'

// 获取工作流分页列表请求
export type GetWorkflowsWithPageRequest = BasePaginatorRequest & {
  search_word?: string
  status?: string
}

// 获取工作流分页列表响应
export type GetWorkflowsWithPageResponse = BasePaginatorResponse<{
  id: string
  name: string
  tool_call_name: string
  icon: string
  description: string
  status: string
  is_debug_passed: boolean
  node_count: number
  creator_name: string
  creator_avatar: string
  published_at: number
  updated_at: number
  created_at: number
}>

// 新增工作流请求
export type CreateWorkflowRequest = {
  name: string
  tool_call_name: string
  icon: string
  description: string
}

// 修改工作流基础信息请求
export type UpdateWorkflowRequest = {
  name: string
  tool_call_name: string
  icon: string
  description: string
}

// 获取工作流基础信息响应
export type GetWorkflowResponse = BaseResponse<{
  id: string
  name: string
  tool_call_name: string
  icon: string
  description: string
  status: string
  is_debug_passed: boolean
  node_count: number
  published_at: number
  updated_at: number
  created_at: number
}>

// 获取指定工作流图草稿配置
export type GetDraftGraphResponse = BaseResponse<{
  nodes: Record<string, any>[]
  edges: Record<string, any>[]
}>

// 更新指定工作流图草稿配置
export type UpdateDraftGraphRequest = {
  nodes: Record<string, any>[]
  edges: Record<string, any>[]
}

// 工作流运行追踪步骤与追踪详情响应
export type WorkflowResultTraceStep = {
  id: string
  node_data: {
    id: string
    node_type: string
    title: string
    inputs?: Record<string, any>
    outputs?: Record<string, any>
  }
  status: string
  error?: string
  latency?: number
  created_at: number
}

export type WorkflowResultTraceData = {
  id: string
  workflow_id: string
  status: string
  latency: number
  created_at: number
  updated_at: number
  steps: WorkflowResultTraceStep[]
}

export type GetWorkflowResultTraceResponse = BaseResponse<WorkflowResultTraceData>
