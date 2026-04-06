import { ref, onUnmounted } from 'vue'
import { getNotifications } from '@/services/notification'
import type { DocumentIndexNotification } from '@/models/notification'

const isDocumentIndexNotification = (notification: unknown): notification is DocumentIndexNotification => {
  return (
    typeof notification === 'object' &&
    notification !== null &&
    'dataset_id' in notification &&
    'document_id' in notification
  )
}

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
        (notification): notification is DocumentIndexNotification =>
          isDocumentIndexNotification(notification) &&
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
    if (pollTimer) {
      return
    }

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
