<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, type Ref } from 'vue'
import DocumentIndexNotification from '@/components/DocumentIndexNotification.vue'
import AgentNotification from '@/components/AgentNotification.vue'
import { useDocumentIndexNotificationWebSocket } from '@/hooks/use-document-index-notification-websocket'
import { useDocumentIndexNotificationPolling } from '@/hooks/use-document-index-notification-polling'
import { useAgentNotificationWebSocket } from '@/hooks/use-agent-notification-websocket'
import { useAgentNotificationPolling } from '@/hooks/use-agent-notification-polling'
import type { DocumentIndexNotification as DocumentNotificationType } from '@/models/notification'
import type { AgentNotification as AgentNotificationType } from '@/models/agent-notification'

// 获取通知组件的引用
const documentNotificationRef = ref<InstanceType<typeof DocumentIndexNotification>>()
const agentNotificationRef = ref<InstanceType<typeof AgentNotification>>()
const POLLING_FALLBACK_DELAY = 3000

// 初始化文档索引通知 WebSocket 监听
const {
  subscribeToNotifications,
  isEnabled: isDocumentNotificationEnabled,
  isReady: isDocumentNotificationReady,
} = useDocumentIndexNotificationWebSocket()

// 初始化文档索引通知轮询备选方案
const { startPolling, stopPolling } = useDocumentIndexNotificationPolling()

// 初始化 Agent 通知 WebSocket 监听
const {
  subscribeToNotifications: subscribeToAgentNotifications,
  isEnabled: isAgentNotificationEnabled,
  isReady: isAgentNotificationReady,
} = useAgentNotificationWebSocket()

// 初始化 Agent 通知轮询备选方案
const { startPolling: startAgentPolling, stopPolling: stopAgentPolling } = useAgentNotificationPolling()

const handleDocumentNotifications = (notifications: DocumentNotificationType[]) => {
  notifications.forEach((notification) => {
    documentNotificationRef.value?.addNotification(notification)
  })
}

const handleAgentNotifications = (notifications: AgentNotificationType[]) => {
  notifications.forEach((notification) => {
    agentNotificationRef.value?.addNotification(notification)
  })
}

const createPollingFallbackController = (
  isEnabled: Ref<boolean>,
  isReady: Ref<boolean>,
  start: () => void,
  stop: () => void,
) => {
  let fallbackTimer: ReturnType<typeof setTimeout> | null = null
  let hasBeenReady = false

  const clearFallbackTimer = () => {
    if (!fallbackTimer) {
      return
    }

    clearTimeout(fallbackTimer)
    fallbackTimer = null
  }

  const startFallback = () => {
    if (hasBeenReady) {
      start()
      return
    }

    if (fallbackTimer) {
      return
    }

    fallbackTimer = setTimeout(() => {
      fallbackTimer = null
      if (!isReady.value) {
        start()
      }
    }, POLLING_FALLBACK_DELAY)
  }

  const stopFallback = () => {
    clearFallbackTimer()
    stop()

    if (isReady.value) {
      hasBeenReady = true
    }
  }

  watch(
    [isEnabled, isReady],
    ([enabled, ready]) => {
      if (!enabled) {
        stopFallback()
        return
      }

      if (ready) {
        stopFallback()
        return
      }

      startFallback()
    },
    { immediate: true },
  )

  return () => {
    clearFallbackTimer()
    stop()
  }
}

const stopDocumentPollingFallback = createPollingFallbackController(
  isDocumentNotificationEnabled,
  isDocumentNotificationReady,
  () => {
    startPolling(handleDocumentNotifications)
  },
  stopPolling,
)

const stopAgentPollingFallback = createPollingFallbackController(
  isAgentNotificationEnabled,
  isAgentNotificationReady,
  () => {
    startAgentPolling(handleAgentNotifications)
  },
  stopAgentPolling,
)

onMounted(() => {
  // 订阅文档索引完成通知（WebSocket 优先）
  subscribeToNotifications((notification: DocumentNotificationType) => {
    documentNotificationRef.value?.addNotification(notification)
  })

  // 订阅 Agent 完成通知
  subscribeToAgentNotifications((notification: AgentNotificationType) => {
    agentNotificationRef.value?.addNotification(notification)
  })
})

onUnmounted(() => {
  stopDocumentPollingFallback()
  stopAgentPollingFallback()
})
</script>

<template>
  <div class="h-full w-full flex flex-col">
    <!-- 文档索引完成通知组件 -->
    <document-index-notification ref="documentNotificationRef" />

    <!-- Agent 构建完成通知组件 -->
    <agent-notification ref="agentNotificationRef" />

    <!-- 路由视图 -->
    <router-view />
  </div>
</template>

<style scoped></style>
