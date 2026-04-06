import { computed, ref, watch, onUnmounted } from 'vue'
import { useCredentialStore } from '@/stores/credential'
import { getCredentialAccessToken } from '@/utils/auth'
import type { DocumentIndexNotification } from '@/models/notification'
import io, { Socket } from 'socket.io-client'

type SubscriptionAck = {
  ok?: boolean
  channel?: string
  error?: string
}

const SUBSCRIBE_ACK_TIMEOUT_MS = 5000

export const useDocumentIndexNotificationWebSocket = () => {
  const credentialStore = useCredentialStore()
  const socket = ref<Socket | null>(null)
  const isConnected = ref(false)
  const subscribedChannel = ref('')
  const accessToken = computed(() => getCredentialAccessToken(credentialStore.credential))
  const isEnabled = computed(() => Boolean(accessToken.value))

  const subscribeNotifications = () => {
    if (!socket.value?.connected || !isEnabled.value || subscribedChannel.value) {
      return
    }

    socket.value.timeout(SUBSCRIBE_ACK_TIMEOUT_MS).emit(
      'subscribe_document_index_notification',
      (error: Error | null, response?: SubscriptionAck) => {
        if (error || !response?.ok || !response.channel) {
          subscribedChannel.value = ''
          console.warn('[WebSocket] Failed to subscribe document notifications:', error || response)
          return
        }

        subscribedChannel.value = response.channel
      },
    )
  }

  const unsubscribeNotifications = () => {
    if (!socket.value || !subscribedChannel.value) {
      subscribedChannel.value = ''
      return
    }

    if (socket.value.connected) {
      socket.value.emit('unsubscribe_document_index_notification')
    }

    subscribedChannel.value = ''
  }

  const updateSocketAuth = () => {
    if (!socket.value) {
      return
    }

    socket.value.auth = {
      token: accessToken.value,
    }
  }

  const initializeSocket = () => {
    if (socket.value || !isEnabled.value) {
      return
    }

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001'

    socket.value = io(apiUrl, {
      auth: (callback) => {
        callback({
          token: accessToken.value,
        })
      },
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    })

    // 连接成功
    socket.value.on('connect', () => {
      isConnected.value = true
      subscribedChannel.value = ''
      console.log('[WebSocket] Connected')

      subscribeNotifications()
    })

    // 连接断开
    socket.value.on('disconnect', () => {
      isConnected.value = false
      subscribedChannel.value = ''
      console.log('[WebSocket] Disconnected')
    })

    // 连接错误
    socket.value.on('connect_error', (error) => {
      isConnected.value = false
      subscribedChannel.value = ''
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
      unsubscribeNotifications()
      socket.value.disconnect()
      socket.value = null
      isConnected.value = false
      subscribedChannel.value = ''
    }
  }

  watch(
    accessToken,
    (nextToken, previousToken) => {
      if (!nextToken) {
        disconnect()
        return
      }

      if (!socket.value) {
        initializeSocket()
        return
      }

      updateSocketAuth()

      if (previousToken && previousToken !== nextToken && socket.value.connected) {
        subscribedChannel.value = ''
        socket.value.disconnect()
        socket.value.connect()
        return
      }

      if (!socket.value.connected) {
        socket.value.connect()
        return
      }

      subscribeNotifications()
    },
    { immediate: true },
  )

  onUnmounted(() => {
    disconnect()
  })

  return {
    socket,
    isConnected,
    isEnabled,
    isReady: computed(() => isEnabled.value && isConnected.value && Boolean(subscribedChannel.value)),
    initializeSocket,
    subscribeToNotifications,
    disconnect,
  }
}
