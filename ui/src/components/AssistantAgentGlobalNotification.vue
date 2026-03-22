<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getAssistantAgentConversations } from '@/services/assistant-agent'
import type { AssistantAgentConversation } from '@/models/assistant-agent'

const router = useRouter()

// 通知列表
const notifications = ref<AssistantAgentConversation[]>([])

// 轮询定时器
let pollTimer: ReturnType<typeof setInterval> | null = null

// 轮询间隔（毫秒）
const POLL_INTERVAL = 3000

/**
 * 拉取通知
 */
const fetchNotifications = async () => {
  try {
    const response = await getAssistantAgentConversations(10)
    if (response.data && response.data.length > 0) {
      // 添加新通知到列表
      notifications.value.unshift(...response.data)

      // 为每个新通知显示消息提示
      response.data.forEach((notification: AssistantAgentConversation) => {
        Message.info({
          content: notification.name,
          duration: 3,
        })
      })
    }
  } catch (error) {
    console.error('Failed to fetch notifications:', error)
  }
}

/**
 * 处理通知点击
 */
const handleNotificationClick = (notification: AssistantAgentConversation) => {
  // 导航到对话
  router.push({
    path: '/home',
    query: { conversation_id: notification.id },
  })
  // 移除已点击的通知
  notifications.value = notifications.value.filter((n) => n.id !== notification.id)
}

/**
 * 关闭通知
 */
const handleCloseNotification = (notification: AssistantAgentConversation) => {
  notifications.value = notifications.value.filter((n) => n.id !== notification.id)
}

/**
 * 启动轮询
 */
const startPolling = () => {
  // 立即拉取一次
  fetchNotifications()

  // 设置定时轮询
  pollTimer = setInterval(() => {
    fetchNotifications()
  }, POLL_INTERVAL)
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
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="fixed top-4 right-4 z-50 flex flex-col gap-3 max-w-sm">
    <transition-group name="notification" tag="div" class="flex flex-col gap-3">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        class="bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden hover:shadow-xl transition-shadow duration-200"
      >
        <div class="p-4 flex items-start gap-3">
          <!-- 左侧图标 -->
          <div class="flex-shrink-0 mt-0.5">
            <div class="w-2 h-2 rounded-full bg-blue-500"></div>
          </div>

          <!-- 中间内容 -->
          <div class="flex-1 min-w-0">
            <h3 class="text-sm font-semibold text-gray-900 truncate">
              {{ notification.name }}
            </h3>
            <p class="text-xs text-gray-600 mt-1 line-clamp-2">
              {{ notification.is_active ? '活跃' : '已关闭' }}
            </p>
          </div>

          <!-- 右侧关闭按钮 -->
          <button
            class="flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors"
            @click="handleCloseNotification(notification)"
          >
            <icon-close :size="16" />
          </button>
        </div>

        <!-- 底部操作栏 -->
        <div class="px-4 py-2 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
          <span class="text-xs text-gray-500">
            {{ new Date(notification.updated_at * 1000).toLocaleTimeString() }}
          </span>
          <button
            class="text-xs font-medium text-blue-600 hover:text-blue-700 transition-colors"
            @click="handleNotificationClick(notification)"
          >
            查看详情 →
          </button>
        </div>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.notification-enter-active,
.notification-leave-active {
  transition: all 0.3s ease;
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
