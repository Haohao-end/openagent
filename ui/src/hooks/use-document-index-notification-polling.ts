import { ref, onMounted, onUnmounted } from 'vue'
import { getNotifications } from '@/services/notification'
import type { DocumentIndexNotification } from '@/models/notification'

export const useDocumentIndexNotificationPolling = () => {
  const notifications = ref<DocumentIndexNotification[]>([])
  const isLoading = ref(false)
  let pollTimer: ReturnType<typeof setInterval> | null = null

  /**
   * 拉取通知
   */
  const fetchNotifications = async (): Promise<DocumentIndexNotification[]> => {
    if (isLoading.value) {
      return []
    }

    try {
      isLoading.value = true
      const response = await getNotifications(1, 10, 'document')
      const notificationList = Array.isArray(response.list) ? response.list : []

      return notificationList.filter(
        (notification: DocumentIndexNotification) =>
          Boolean(notification.dataset_id && notification.document_id) && !notification.is_read,
      )
    } catch (error) {
      console.error('Failed to fetch notifications:', error)
    } finally {
      isLoading.value = false
    }

    return []
  }

  /**
   * 启动轮询
   */
  const startPolling = (callback: (notifications: DocumentIndexNotification[]) => void) => {
    // 立即拉取一次
    fetchNotifications().then((newNotifications) => {
      if (newNotifications.length > 0) {
        callback(newNotifications)
      }
    })

    // 设置 5 秒轮询一次
    pollTimer = setInterval(async () => {
      const newNotifications = await fetchNotifications()
      if (newNotifications.length > 0) {
        callback(newNotifications)
      }
    }, 5000)
  }

  /**
   * 停止轮询
   */
  const stopPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  onMounted(() => {
    // 注意：这里不自动启动轮询，由使用者决定何时启动
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    notifications,
    isLoading,
    fetchNotifications,
    startPolling,
    stopPolling,
  }
}
