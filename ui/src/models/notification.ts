/**
 * 文档索引完成通知模型
 */
export interface DocumentIndexNotification {
  id: string
  user_id: string
  dataset_id: string
  document_id: string
  document_name: string
  segment_count: number
  index_duration: number // 索引耗时（秒）
  created_at: string | number
  status: 'success' | 'error' // 成功或错误
  error_message?: string // 错误信息
  is_read: boolean
}
