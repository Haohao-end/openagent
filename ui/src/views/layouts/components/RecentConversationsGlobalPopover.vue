<script setup lang="ts">
import type { RecentConversation } from '@/models/conversation'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

interface Props {
  conversations: RecentConversation[]
  loading: boolean
}

const props = withDefaults(defineProps<Props>(), {
  conversations: () => [],
  loading: false,
})

const router = useRouter()
const isHovering = ref(false)
let hoverTimeout: ReturnType<typeof setTimeout> | null = null

// 格式化相对时间
const formatRelativeTime = (timestamp: number) => {
  const now = Math.floor(Date.now() / 1000)
  const diff = now - timestamp

  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 604800) return `${Math.floor(diff / 86400)}天前`
  return `${Math.floor(diff / 604800)}周前`
}

// 获取消息预览
const getMessagePreview = (conversation: RecentConversation) => {
  const message = conversation.human_message || conversation.ai_message || '暂无消息'
  return message.length > 40 ? `${message.substring(0, 40)}...` : message
}

// 获取用户消息预览
const getHumanMessagePreview = (conversation: RecentConversation) => {
  if (!conversation.human_message) return ''
  const message = conversation.human_message
  return message.length > 50 ? `${message.substring(0, 50)}...` : message
}

// 获取AI消息预览
const getAiMessagePreview = (conversation: RecentConversation) => {
  if (!conversation.ai_message) return ''
  const message = conversation.ai_message
  return message.length > 50 ? `${message.substring(0, 50)}...` : message
}

// 显示的对话列表（显示所有对话）
const displayConversations = computed(() => {
  return props.conversations
})

// 处理鼠标进入
const handleMouseEnter = () => {
  if (hoverTimeout) clearTimeout(hoverTimeout)
  isHovering.value = true
}

// 处理鼠标离开
const handleMouseLeave = () => {
  if (hoverTimeout) clearTimeout(hoverTimeout)
  hoverTimeout = setTimeout(() => {
    isHovering.value = false
    window.dispatchEvent(new CustomEvent('recent-conversations:hide'))
  }, 200)
}

// 处理卡片点击
const handleCardClick = async (conversation: RecentConversation) => {
  if (hoverTimeout) clearTimeout(hoverTimeout)
  if (conversation.source_type === 'assistant_agent') {
    await router.push({
      path: '/home',
      query: { conversation_id: conversation.id },
    })
  } else if (conversation.source_type === 'app_debugger' && conversation.app_id) {
    await router.push({
      path: `/space/apps/${conversation.app_id}`,
      query: {
        conversation_id: conversation.id,
        message_id: conversation.message_id,
      },
    })
  }
  window.dispatchEvent(new CustomEvent('recent-conversations:hide'))
}

// 跳转到历史对话列表
const goToConversationHistory = async () => {
  if (hoverTimeout) clearTimeout(hoverTimeout)
  await router.push('/search')
  window.dispatchEvent(new CustomEvent('recent-conversations:hide'))
}

// 监听按钮离开事件
onMounted(() => {
  // 不需要额外的事件监听，Popover 自己管理状态
})

onUnmounted(() => {
  if (hoverTimeout) clearTimeout(hoverTimeout)
})
</script>

<template>
  <!-- 全屏 Popover - 不受侧边栏限制 -->
  <div
    id="recent-conversations-popover"
    class="w-80 max-h-[calc(100vh-24px)] bg-white rounded-lg shadow-2xl border border-gray-200 z-[9999] overflow-hidden flex flex-col"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <!-- 标题栏 -->
    <div class="px-4 py-3 border-b border-gray-200 bg-gray-50 flex-shrink-0">
      <div class="flex items-center justify-between">
        <div class="text-sm font-bold text-gray-700">最近对话</div>
        <div class="text-xs text-gray-500">{{ conversations.length }} 条</div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="p-4 flex-shrink-0">
      <a-skeleton :loading="true" animation>
        <a-skeleton-line :rows="3" :line-height="20" :line-spacing="12" />
      </a-skeleton>
    </div>

    <!-- 空状态 -->
    <div v-else-if="conversations.length === 0" class="p-4 text-center text-sm text-gray-400 flex-shrink-0">
      暂无最近对话
    </div>

    <!-- 对话列表 -->
    <div v-else class="flex-1 min-h-0 overflow-y-auto">
      <div
        v-for="conversation in displayConversations"
        :key="conversation.id"
        class="px-4 py-3 border-b border-gray-100 last:border-b-0 hover:bg-blue-50 cursor-pointer transition-colors duration-150"
        @click="handleCardClick(conversation)"
      >
        <!-- 对话头部 -->
        <div class="flex items-start gap-2 mb-2">
          <div class="flex-shrink-0 mt-0.5">
            <icon-message
              v-if="conversation.source_type === 'assistant_agent'"
              class="w-4 h-4 text-gray-400"
            />
            <icon-apps v-else class="w-4 h-4 text-gray-400" />
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-medium text-sm text-gray-900 truncate">
              {{ conversation.name }}
            </div>
            <div class="text-xs text-gray-500 mt-0.5">
              {{ conversation.app_name || '助手' }}
            </div>
          </div>
        </div>

        <!-- 消息预览 -->
        <div class="ml-6 space-y-1">
          <!-- 用户消息 -->
          <div v-if="conversation.human_message" class="flex gap-1.5">
            <span class="text-xs font-medium text-gray-500 flex-shrink-0">用户:</span>
            <div class="text-xs text-gray-600 line-clamp-1 flex-1">
              {{ getHumanMessagePreview(conversation) }}
            </div>
          </div>
          <!-- AI消息 -->
          <div v-if="conversation.ai_message" class="flex gap-1.5">
            <span class="text-xs font-medium text-gray-500 flex-shrink-0">AI:</span>
            <div class="text-xs text-gray-600 line-clamp-1 flex-1">
              {{ getAiMessagePreview(conversation) }}
            </div>
          </div>
        </div>

        <!-- 时间戳 -->
        <div class="ml-6 text-xs text-gray-400 mt-1.5">
          {{ formatRelativeTime(conversation.latest_message_at) }}
        </div>
      </div>
    </div>

    <!-- 查看全部按钮 - 固定在底部 -->
    <div
      class="px-4 py-3 text-center border-t border-gray-200 bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors duration-150 flex-shrink-0"
      @click="goToConversationHistory"
    >
      <div class="text-sm text-blue-600 font-medium">查看全部对话</div>
    </div>
  </div>
</template>

<style scoped>
/* 自定义滚动条 */
div::-webkit-scrollbar {
  width: 6px;
}

div::-webkit-scrollbar-track {
  background: transparent;
}

div::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}

div::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
