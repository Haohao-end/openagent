import { ref, onMounted, onUnmounted } from 'vue'
import { useAccountStore } from '@/stores/account'
import type { DocumentIndexNotification } from '@/models/notification'
import io, { Socket } from 'socket.io-client'

export const useDocumentIndexNotificationWebSocket = () => {
  const accountStore = useAccountStore()
  const socket = ref<Socket | null>(null)
  const isConnected = ref(false)

  /**
   * 初始化 WebSocket 连接
   */
  const initializeSocket = () => {
    if (socket.value) {
      return
    }

    // 获取 API 基础 URL
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001'

    socket.value = io(apiUrl, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    })

    // 连接成功
    socket.value.on('connect', () => {
      isConnected.value = true
      console.log('[WebSocket] Connected')

      // 订阅文档索引通知
      if (accountStore.account.id) {
        socket.value?.emit('subscribe_document_index_notification', {
          user_id: accountStore.account.id,
        })
      }
    })

    // 连接断开
    socket.value.on('disconnect', () => {
      isConnected.value = false
      console.log('[WebSocket] Disconnected')
    })

    // 连接错误
    socket.value.on('connect_error', (error) => {
      console.error('[WebSocket] Connection error:', error)
    })
  }

  /**
   * 订阅文档索引完成通知
   */
  const subscribeToNotifications = (callback: (notification: DocumentIndexNotification) => void) => {
    if (!socket.value) {
      initializeSocket()
    }

    socket.value?.on('document_index_notification', (notification: DocumentIndexNotification) => {
      console.log('[WebSocket] Received notification:', notification)
      callback(notification)
    })
  }

  /**
   * 断开连接
   */
  const disconnect = () => {
    if (socket.value) {
      socket.value.disconnect()
      socket.value = null
      isConnected.value = false
    }
  }

  onMounted(() => {
    initializeSocket()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    socket,
    isConnected,
    initializeSocket,
    subscribeToNotifications,
    disconnect,
  }
}
