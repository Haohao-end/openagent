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

type NotificationSocketOptions = {
  connectLogMessage: string
  notificationEvent: string
  subscribeEvent: string
  subscribeFailureLogMessage: string
  unsubscribeEvent: string
}

type NotificationHandler<TNotification> = (notification: TNotification) => void

const SUBSCRIBE_ACK_TIMEOUT_MS = 5000

export const createNotificationWebSocket = <TNotification>(
  options: NotificationSocketOptions,
) => {
  return () => {
    const credentialStore = useCredentialStore()
    const socket = ref<Socket | null>(null)
    const isConnected = ref(false)
    const subscribedChannel = ref('')
    let subscriptionGeneration = 0
    const notificationHandler = ref<NotificationHandler<TNotification> | null>(null)
    const notificationCallback = ref<NotificationHandler<TNotification> | null>(null)
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

      const currentSocket = socket.value
      const token = accessToken.value
      const generation = ++subscriptionGeneration
      currentSocket.timeout(SUBSCRIBE_ACK_TIMEOUT_MS).emit(
        options.subscribeEvent,
        (error: Error | null, response?: SubscriptionAck) => {
          if (generation !== subscriptionGeneration || socket.value !== currentSocket ||
              accessToken.value !== token || !currentSocket.connected) return
          if (error || !response?.ok || !response.channel) {
            subscribedChannel.value = ''
            console.warn(options.subscribeFailureLogMessage, error?.name || 'server_rejected')
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
        // Avoid polling->websocket upgrade races; App.vue already falls back to HTTP polling.
        transports: ['websocket'],
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
        subscriptionGeneration++
        isConnected.value = false
        subscribedChannel.value = ''
        console.log('[WebSocket] Disconnected')
      })

      socket.value.on('connect_error', (error) => {
        subscriptionGeneration++
        isConnected.value = false
        subscribedChannel.value = ''
        console.error('[WebSocket] Connection error:', error.name)
      })
      if (notificationCallback.value) {
        const handler = (notification: TNotification) => notificationCallback.value?.(notification)
        notificationHandler.value = handler
        socket.value.on(options.notificationEvent, handler)
      }
    }

    const subscribeToNotifications = (callback: (notification: TNotification) => void) => {
      notificationCallback.value = callback
      if (!socket.value) {
        initializeSocket()
      }

      if (!socket.value) {
        return
      }

      removeNotificationListener()

      const handler = (notification: TNotification) => {
        callback(notification)
      }

      notificationHandler.value = handler
      socket.value.on(options.notificationEvent, handler)
    }

    const disconnect = () => {
      subscriptionGeneration++
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
      notificationCallback.value = null
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
