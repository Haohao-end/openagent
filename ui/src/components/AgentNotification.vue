<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { markNotificationAsRead } from '@/services/notification'
import type { AgentNotification } from '@/models/agent-notification'

const router = useRouter()

// 通知列表
const notifications = ref<AgentNotification[]>([])

// 自动消失的定时器映射
const autoHideTimers = ref<Map<string, ReturnType<typeof setTimeout>>>(new Map())

// 点击后消失的定时器映射
const clickHideTimers = ref<Map<string, ReturnType<typeof setTimeout>>>(new Map())

/**
 * 清理所有定时器
 */
const clearAllTimers = () => {
  autoHideTimers.value.forEach((timer) => {
    clearTimeout(timer)
  })
  autoHideTimers.value.clear()

  clickHideTimers.value.forEach((timer) => {
    clearTimeout(timer)
  })
  clickHideTimers.value.clear()
}

/**
 * 添加通知
 */
const addNotification = (notification: AgentNotification) => {
  // 检查是否已存在相同的通知
  const exists = notifications.value.some((n) => n.id === notification.id)
  if (exists) {
    return
  }

  notifications.value.push(notification)

  markNotificationAsRead(notification.id).catch((error) => {
    console.warn('Failed to mark agent notification as read:', error)
  })

  // 设置 10 秒后自动消失
  const timer = setTimeout(() => {
    removeNotification(notification.id)
  }, 10000)

  autoHideTimers.value.set(notification.id, timer)
}

/**
 * 移除通知
 */
const removeNotification = (notificationId: string) => {
  notifications.value = notifications.value.filter((n) => n.id !== notificationId)

  // 清理自动消失定时器
  const autoTimer = autoHideTimers.value.get(notificationId)
  if (autoTimer) {
    clearTimeout(autoTimer)
    autoHideTimers.value.delete(notificationId)
  }

  // 清理点击消失定时器
  const clickTimer = clickHideTimers.value.get(notificationId)
  if (clickTimer) {
    clearTimeout(clickTimer)
    clickHideTimers.value.delete(notificationId)
  }
}

/**
 * 处理通知点击
 */
const handleNotificationClick = (notification: AgentNotification) => {
  // 清理自动消失定时器
  const autoTimer = autoHideTimers.value.get(notification.id)
  if (autoTimer) {
    clearTimeout(autoTimer)
    autoHideTimers.value.delete(notification.id)
  }

  // 导航到Agent调试页面
  router.push({
    path: `/space/apps/${notification.app_id}`,
  })

  // 设置 2 秒后消失
  const clickTimer = setTimeout(() => {
    removeNotification(notification.id)
  }, 2000)

  clickHideTimers.value.set(notification.id, clickTimer)
}

/**
 * 处理关闭按钮点击
 */
const handleCloseNotification = (notificationId: string) => {
  removeNotification(notificationId)
}

// 组件卸载时清理所有定时器
onUnmounted(() => {
  clearAllTimers()
})

// 暴露方法给外部使用
defineExpose({
  addNotification,
})
</script>

<template>
  <div class="fixed top-4 right-4 z-50 flex flex-col gap-3 max-w-lg">
    <transition-group name="notification" tag="div" class="flex flex-col gap-3">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        class="bg-white rounded-lg shadow-md border border-green-200 overflow-hidden hover:shadow-lg transition-shadow duration-200 cursor-pointer"
        @click="handleNotificationClick(notification)"
      >
        <!-- 主要内容 -->
        <div class="p-5 flex items-start gap-3">
          <!-- 左侧图标 - 绿色成功风格 -->
          <div class="flex-shrink-0 mt-1">
            <div class="w-3 h-3 rounded-full bg-green-500"></div>
          </div>

          <!-- 中间内容 -->
          <div class="flex-1 min-w-0">
            <p class="text-base font-medium text-gray-900 mb-1">
              Agent构建完成
            </p>
            <p class="text-sm text-gray-600 truncate">
              {{ notification.app_name }}
            </p>
          </div>

          <!-- 右侧关闭按钮 -->
          <button
            class="flex-shrink-0 text-gray-300 hover:text-gray-500 transition-colors mt-0.5"
            @click.stop="handleCloseNotification(notification.id)"
          >
            <icon-close :size="16" />
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
</style>
