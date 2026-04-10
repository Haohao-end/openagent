import { computed, onUnmounted, ref, watch } from 'vue'
import { socketConnectionUrl, socketPath } from '@/config'
import { useCredentialStore } from '@/stores/credential'
import { getCredentialAccessToken } from '@/utils/auth'
import io, { Socket } from 'socket.io-client'

type SubscriptionAck = {
  ok?: boolean
  channel?: string
  error?: string
}

type NotificationSocketOptions<TNotification> = {
  connectLogMessage: string
  notificationEvent: string
  receiveLogMessage: string
  subscribeEvent: string
  subscribeFailureLogMessage: string
  unsubscribeEvent: string
}

type NotificationHandler<TNotification> = (notification: TNotification) => void

const SUBSCRIBE_ACK_TIMEOUT_MS = 5000

export const createNotificationWebSocket = <TNotification>(
  options: NotificationSocketOptions<TNotification>,
) => {
  return () => {
    const credentialStore = useCredentialStore()
    const socket = ref<Socket | null>(null)
    const isConnected = ref(false)
    const subscribedChannel = ref('')
    const notificationHandler = ref<NotificationHandler<TNotification> | null>(null)
    const accessToken = computed(() => getCredentialAccessToken(credentialStore.credential))
    const isEnabled = computed(() => Boolean(accessToken.value))

    const removeNotificationListener = () => {
      if (!socket.value || !notificationHandler.value) {
        notificationHandler.value = null
        return
      }

      socket.value.off(options.notificationEvent, notificationHandler.value)
      notificationHandler.value = null
    }

    const subscribeNotifications = () => {
      if (!socket.value?.connected || !isEnabled.value || subscribedChannel.value) {
        return
      }

      socket.value.timeout(SUBSCRIBE_ACK_TIMEOUT_MS).emit(
        options.subscribeEvent,
        (error: Error | null, response?: SubscriptionAck) => {
          if (error || !response?.ok || !response.channel) {
            subscribedChannel.value = ''
            console.warn(options.subscribeFailureLogMessage, error || response)
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
        socket.value.emit(options.unsubscribeEvent)
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

      socket.value = io(socketConnectionUrl, {
        auth: (callback) => {
          callback({
            token: accessToken.value,
          })
        },
        path: socketPath,
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
      })

      socket.value.on('connect', () => {
        isConnected.value = true
        subscribedChannel.value = ''
        console.log(options.connectLogMessage)
        subscribeNotifications()
      })

      socket.value.on('disconnect', () => {
        isConnected.value = false
        subscribedChannel.value = ''
        console.log('[WebSocket] Disconnected')
      })

      socket.value.on('connect_error', (error) => {
        isConnected.value = false
        subscribedChannel.value = ''
        console.error('[WebSocket] Connection error:', error)
      })
    }

    const subscribeToNotifications = (callback: (notification: TNotification) => void) => {
      if (!socket.value) {
        initializeSocket()
      }

      if (!socket.value) {
        return
      }

      removeNotificationListener()

      const handler = (notification: TNotification) => {
        console.log(options.receiveLogMessage, notification)
        callback(notification)
      }

      notificationHandler.value = handler
      socket.value.on(options.notificationEvent, handler)
    }

    const disconnect = () => {
      if (!socket.value) {
        return
      }

      removeNotificationListener()
      unsubscribeNotifications()
      socket.value.disconnect()
      socket.value = null
      isConnected.value = false
      subscribedChannel.value = ''
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
}
