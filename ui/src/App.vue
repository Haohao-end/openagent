<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
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

// 初始化文档索引通知 WebSocket 监听
const { subscribeToNotifications } = useDocumentIndexNotificationWebSocket()

// 初始化文档索引通知轮询备选方案
const { startPolling, stopPolling } = useDocumentIndexNotificationPolling()

// 初始化 Agent 通知 WebSocket 监听
const { subscribeToNotifications: subscribeToAgentNotifications } = useAgentNotificationWebSocket()

// 初始化 Agent 通知轮询备选方案
const { startPolling: startAgentPolling, stopPolling: stopAgentPolling } = useAgentNotificationPolling()

onMounted(() => {
  // 订阅文档索引完成通知（WebSocket 优先）
  subscribeToNotifications((notification: DocumentNotificationType) => {
    documentNotificationRef.value?.addNotification(notification)
  })

  // 启动文档索引通知轮询备选方案（WebSocket 连接失败时作为备选）
  startPolling((notifications: DocumentNotificationType[]) => {
    notifications.forEach((notification) => {
      documentNotificationRef.value?.addNotification(notification)
    })
  })

  // 订阅 Agent 完成通知
  subscribeToAgentNotifications((notification: AgentNotificationType) => {
    agentNotificationRef.value?.addNotification(notification)
  })

  // 启动 Agent 通知轮询备选方案（WebSocket 连接失败时作为备选）
  startAgentPolling((notifications: AgentNotificationType[]) => {
    notifications.forEach((notification) => {
      agentNotificationRef.value?.addNotification(notification)
    })
  })
})

onUnmounted(() => {
  stopPolling()
  stopAgentPolling()
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
