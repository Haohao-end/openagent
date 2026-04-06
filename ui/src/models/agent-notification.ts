/**
 * Agent构建完成通知模型
 */
export interface AgentNotification {
  id: string
  user_id: string
  app_id: string
  app_name: string
  created_at: string | number
  is_read: boolean
}
