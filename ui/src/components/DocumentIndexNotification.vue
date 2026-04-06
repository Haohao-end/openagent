<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import router from '@/router'
import { markNotificationAsRead } from '@/services/notification'
import type { DocumentIndexNotification } from '@/models/notification'

// 通知列表
const notifications = ref<DocumentIndexNotification[]>([])

// 自动消失的定时器映射
const autoHideTimers = ref<Map<string, ReturnType<typeof setTimeout>>>(new Map())

const clearAllTimers = () => {
  autoHideTimers.value.forEach((timer) => {
    clearTimeout(timer)
  })
  autoHideTimers.value.clear()
}

/**
 * 获取状态颜色
 */
const getStatusColor = (status: string): string => {
  return status === 'success' ? 'bg-green-500' : 'bg-red-500'
}

/**
 * 添加通知
 */
const addNotification = (notification: DocumentIndexNotification) => {
  // 检查是否已存在相同的通知（当前显示中）
  const exists = notifications.value.some((n) => n.id === notification.id)
  if (exists) {
    return
  }

  notifications.value.push(notification)

  // 立即标记为已读（调用后端 API）
  // 即使失败也不重试，只在前端标记为已显示
  Promise.resolve(markNotificationAsRead(notification.id)).catch((error) => {
    console.warn('Failed to mark notification as read:', error)
    // 不抛出错误，继续显示通知
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

  // 清理定时器
  const timer = autoHideTimers.value.get(notificationId)
  if (timer) {
    clearTimeout(timer)
    autoHideTimers.value.delete(notificationId)
  }
}

/**
 * 处理通知点击
 */
const handleNotificationClick = (notification: DocumentIndexNotification) => {
  // 清理定时器
  const timer = autoHideTimers.value.get(notification.id)
  if (timer) {
    clearTimeout(timer)
    autoHideTimers.value.delete(notification.id)
  }

  // 导航到文档片段列表页面
  router.push({
    name: 'space-datasets-documents-segments-list',
    params: {
      dataset_id: notification.dataset_id,
      document_id: notification.document_id,
    },
  })

  // 2 秒后移除通知
  const delayTimer = setTimeout(() => {
    removeNotification(notification.id)
  }, 2000)

  autoHideTimers.value.set(notification.id, delayTimer)
}

/**
 * 处理关闭按钮点击
 */
const handleCloseNotification = (notificationId: string) => {
  removeNotification(notificationId)
}

onUnmounted(() => {
  clearAllTimers()
})

// 暴露方法给外部使用
defineExpose({
  addNotification,
})
</script>

<template>
  <div class="fixed top-4 right-4 z-40 flex flex-col gap-3 max-w-lg">
    <transition-group name="notification" tag="div" class="flex flex-col gap-3">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        class="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden hover:shadow-lg transition-shadow duration-200 cursor-pointer"
        @click="handleNotificationClick(notification)"
      >
        <!-- 主要内容 -->
        <div class="p-5 flex items-start gap-3">
          <!-- 左侧图标 - 根据状态显示不同颜色 -->
          <div class="flex-shrink-0 mt-1">
            <div :class="['w-3 h-3 rounded-full', getStatusColor(notification.status)]"></div>
          </div>

          <!-- 中间内容 -->
          <div class="flex-1 min-w-0">
            <p class="text-base font-medium text-gray-900 mb-1">
              文档索引{{ notification.status === 'success' ? '完成' : '失败' }}
            </p>
            <p class="text-sm text-gray-600 truncate">
              {{ notification.document_name }}
            </p>
            <!-- 错误信息 -->
            <p v-if="notification.status === 'error' && notification.error_message" class="text-xs text-red-600 mt-1 truncate">
              {{ notification.error_message }}
            </p>
          </div>

          <!-- 右侧关闭按钮 -->
          <button
            class="flex-shrink-0 text-gray-300 hover:text-gray-500 transition-colors mt-0.5"
            aria-label="关闭通知"
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
