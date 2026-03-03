import { type BasePaginatorResponse, type BaseResponse } from '@/models/base'

// 获取知识库分页列表接口响应结构
export type GetDatasetsWithPageResponse = BasePaginatorResponse<{
  id: string
  name: string
  icon: string
  description: string
  document_count: number
  character_count: number
  related_app_count: number
  updated_at: number
  created_at: number
}>

// 新增知识库请求结构
export type CreateDatasetRequest = {
  name: string
  icon: string
  description: string
}

// 更新知识库请求结构
export type UpdateDatasetRequest = {
  name: string
  icon: string
  description: string
}

// 获取知识库详情响应结构
export type GetDatasetResponse = BaseResponse<{
  id: string
  icon: string
  name: string
  description: string
  document_count: number
  hit_count: number
  related_app_count: number
  character_count: number
  updated_at: number
  created_at: number
}>

// 获取指定的知识库文档列表分页请求结构
export type GetDocumentsWithPageRequest = {
  current_page: number
  page_size: number
  search_word: string
}

// 获取指定知识库文档分页列表响应结构
export type GetDocumentsWithPageResponse = BasePaginatorResponse<{
  id: string
  name: string
  character_count: number
  hit_count: number
  position: number
  enabled: boolean
  disabled_at: number
  status: string
  error: string
  updated_at: number
  created_at: number
}>

// 获取指定文档详情响应结构
export type GetDocumentResponse = BaseResponse<{
  id: string
  dataset_id: string
  name: string
  segment_count: number
  character_count: number
  hit_count: number
  position: number
  enabled: boolean
  disabled_at: number
  status: string
  error: string
  updated_at: number
  created_at: number
}>

// 知识库召回测试请求结构
export type HitRequest = {
  retrieval_strategy: string
  k: number
  query: string
  score: number
}

// 知识库召回测试响应结构
export type HitResponse = BaseResponse<
  Array<{
    id: string
    document: {
      id: string
      name: string
      extension: string
      mime_type: string
    }
    dataset_id: string
    score: number
    position: number
    keywords: string[]
    character_count: number
    token_count: number
    hit_count: number
    enabled: boolean
    disabled_at: number
    status: string
    error: string
    updated_at: number
    created_at: number
  }>
>

// 知识库最新查询列表
export type GetDatasetQueriesResponse = BaseResponse<
  Array<{
    id: string
    query: string
    source: string
    dataset_id: string
    created_at: number
  }>
>

// 上传文档列表到知识库的请求结构
export type CreateDocumentsRequest = {
  upload_file_ids: string[]
  process_type: string
  rule: {
    pre_process_rules: {
      id: string
      enabled: boolean
    }[]
    segment: {
      separators: string[]
      chunk_size: number
      chunk_overlap: number
    }
  }
}

// 上传文档列表到知识库的响应结构
export type CreateDocumentsResponse = BaseResponse<{
  batch: string
  documents: {
    id: string
    name: string
    status: string
    created_at: number
  }[]
}>

// 批处理标识获取处理进度响应结构
export type GetDocumentsStatusResponse = BaseResponse<
  Array<{
    id: string
    name: string
    size: number
    extension: string
    mime_type: string
    position: number
    segment_count: number
    completed_segment_count: number
    status: string
    error: string
    processing_started_at: number
    parsing_completed_at: number
    splitting_completed_at: number
    indexing_completed_at: number
    completed_at: number
    stopped_at: number
    created_at: number
  }>
>

// 获取指定文档的片段列表请求结构
export type GetSegmentsWithPageRequest = {
  current_page: number
  page_size: number
  search_word: string
}

// 获取指定文档的片段列表响应结构
export type GetSegmentsWithPageResponse = BasePaginatorResponse<{
  id: string
  dataset_id: string
  document_id: string
  position: number
  content: string
  keywords: string[]
  character_count: number
  token_count: number
  hit_count: number
  enabled: boolean
  disabled_at: number
  status: string
  error: string
  updated_at: number
  created_at: number
}>

// 新增文档片段请求结构
export type CreateSegmentRequest = {
  content: string
  keywords: string[]
}

// 修改文档片段请求结构
export type UpdateSegmentRequest = {
  content: string
  keywords: string[]
}

// 查询文档片段响应结构
export type GetSegmentResponse = BaseResponse<{
  id: string
  document_id: string
  dataset_id: string
  position: number
  content: string
  keywords: string[]
  character_count: number
  token_count: number
  hit_count: number
  hash: string
  enabled: boolean
  status: string
  error: string
  updated_at: number
  created_at: number
}>
