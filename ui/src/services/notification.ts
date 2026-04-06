import { get, post } from '@/utils/request'
import type { AgentNotification } from '@/models/agent-notification'
import type { DocumentIndexNotification } from '@/models/notification'

export type NotificationTypeFilter = 'document' | 'agent'

type NotificationListResponse = {
  list: Array<DocumentIndexNotification | AgentNotification>
  paginator: {
    page: number
    limit: number
    total: number
    total_page: number
  }
}

type ApiEnvelope<T> = {
  data: T
}

/**
 * 获取用户的通知列表
 */
export const getNotifications = async (
  page: number = 1,
  limit: number = 10,
  type?: NotificationTypeFilter,
) => {
  const response = await get<ApiEnvelope<NotificationListResponse>>('/notifications', {
    params: {
      page,
      limit,
      type,
    },
  })
  return response.data
}

/**
 * 标记通知为已读
 */
export const markNotificationAsRead = async (notificationId: string) => {
  const response = await post<ApiEnvelope<{ message: string }>>(`/notifications/${notificationId}/read`)
  return response.data
}

/**
 * 删除通知
 */
export const deleteNotification = async (notificationId: string) => {
  const response = await post<ApiEnvelope<{ message: string }>>(`/notifications/${notificationId}`, {
    body: { _method: 'DELETE' },
  })
  return response.data
}
