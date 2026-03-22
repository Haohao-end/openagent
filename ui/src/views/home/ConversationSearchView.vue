<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import AiDynamicBackground from '@/components/AiDynamicBackground.vue'
import { searchConversations, deleteConversation } from '@/services/conversation-search'
import { useGetRecentConversations, useDeleteConversation } from '@/hooks/use-conversation'
import UpdateConversationNameModal from '@/views/layouts/components/UpdateConversationNameModal.vue'
import type { SearchConversation } from '@/services/conversation-search'
import type { RecentConversation } from '@/models/conversation'

// Type for conversations with message content
type ConversationWithMessages = RecentConversation & {
  human_message: string
  ai_message: string
}

const router = useRouter()

// State
const searchQuery = ref('')
const conversations = ref<SearchConversation[]>([])
const loading = ref(false)
const updateConversationNameVisible = ref(false)
const updateConversationNameId = ref('')
const updateConversationName = ref('')
const visibleMenuId = ref<string | null>(null)

// 最近对话
const {
  loading: recentConversationsLoading,
  conversations: recentConversations,
  loadRecentConversations: loadRecentConversationsHook,
} = useGetRecentConversations()

const { handleDeleteConversation } = useDeleteConversation()

// 关闭菜单
const closeMenu = () => {
  visibleMenuId.value = null
}

// Computed
const filteredConversations = computed(() => {
  // 如果有搜索结果，显示搜索结果
  if (conversations.value.length > 0) {
    return conversations.value
  }
  // 如果没有搜索结果但有最近对话，显示最近对话作为卡片
  if (searchQuery.value.trim() === '' && recentConversations.value && recentConversations.value.length > 0) {
    return recentConversations.value as SearchConversation[]
  }
  return []
})

// Helper to safely get message
const getMessage = (conversation: any, field: string) => {
  if (!conversation) return ''
  const value = conversation[field]
  return value ? String(value) : ''
}

// Methods
const handleSearch = async () => {
  // 如果搜索查询为空，不调用搜索
  if (!searchQuery.value.trim()) {
    conversations.value = []
    return
  }

  loading.value = true
  try {
    const response = await searchConversations(searchQuery.value, 100)
    conversations.value = response.data || []
  } catch (error) {
    console.error('Search failed:', error)
  } finally {
    loading.value = false
  }
}

// 打开编辑名称模态窗
const openUpdateNameModal = (conversation: SearchConversation) => {
  updateConversationNameId.value = conversation.id
  updateConversationName.value = conversation.name
  updateConversationNameVisible.value = true
  visibleMenuId.value = null
}

// 编辑名称成功回调
const updateConversationNameSuccess = (conversation_id: string, name: string) => {
  const conv = conversations.value.find(c => c.id === conversation_id)
  if (conv) {
    conv.name = name
  }
}

// 删除对话
const deleteRecentConversation = (conversation: SearchConversation) => {
  handleDeleteConversation(conversation.id, async () => {
    conversations.value = conversations.value.filter(c => c.id !== conversation.id)
  })
}

const formatDate = (timestamp: number) => {
  // 如果时间戳是秒级别（小于 10000000000），转换为毫秒
  const ms = timestamp < 10000000000 ? timestamp * 1000 : timestamp
  const date = new Date(ms)
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  const day = date.getDate()
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')

  return `${year}年${month}月${day}日 ${hours}:${minutes}`
}

const highlightText = (text: string) => {
  if (!searchQuery.value.trim()) return text

  const query = searchQuery.value.toLowerCase()
  const firstLine = text.split('\n')[0]
  const regex = new RegExp(`(${query})`, 'gi')
  return firstLine.replace(regex, '<span class="gradient-highlight">$1</span>')
}

const truncateText = (text: string, maxLength: number = 100) => {
  if (!text) return ''
  const firstLine = text.split('\n')[0]
  if (firstLine.length > maxLength) {
    return firstLine.substring(0, maxLength) + '...'
  }
  return firstLine
}

const truncateConversationName = (name: string, hasAgent: boolean) => {
  // 如果有agent名称，对话名称最多保留30个字符，否则保留50个字符
  const maxLength = hasAgent ? 30 : 50
  if (name.length > maxLength) {
    return name.substring(0, maxLength) + '...'
  }
  return name
}

const changeConversation = async (conversation: RecentConversation | SearchConversation) => {
  if (!conversation.id) return

  if (conversation.source_type === 'assistant_agent') {
    await router.push({
      path: '/home',
      query: { conversation_id: conversation.id },
    })
    return
  }

  if (conversation.source_type === 'app_debugger' && 'app_id' in conversation && conversation.app_id) {
    await router.push({
      path: `/space/apps/${conversation.app_id}`,
      query: {
        conversation_id: conversation.id,
        message_id: 'message_id' in conversation ? conversation.message_id : undefined,
      },
    })
  }
}

watch(recentConversations, async () => {
  console.log('recentConversations changed:', recentConversations.value.length)
  await nextTick()
  console.log('After nextTick')
}, { deep: true })

watch(searchQuery, () => {
  handleSearch()
}, { debounce: 300 } as any)

onMounted(() => {
  handleSearch()
  loadRecentConversationsHook(20)
})
</script>

<template>
  <div
    key="background-container"
    class="relative w-full h-screen overflow-hidden flex flex-col"
    style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 25%, #f3e8ff 50%, #fce7f3 75%, #f0f9ff 100%);"
    @click="closeMenu"
  >
    <!-- AI 动态背景层 - 使用 key 防止重新渲染 -->
    <div key="background" class="absolute inset-0 z-0 pointer-events-none">
      <AiDynamicBackground
        className=""
        intensity="high"
        :showParticles="true"
        :showGrid="true"
      />
    </div>

    <!-- Main Content -->
    <div class="relative z-10 w-full max-w-[600px] h-full mx-auto px-3 sm:px-4 md:px-0 flex flex-col overflow-hidden">
      <!-- Header and Search - Fixed -->
      <div class="flex-shrink-0 px-4 sm:px-6 pt-6 pb-4">
        <!-- Header -->
        <div class="mb-8 text-center">
          <h1 class="text-4xl font-bold text-gray-900 mb-2">对话历史</h1>
        </div>

        <!-- Search Box -->
        <div class="mb-4">
          <div class="relative">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索对话标题、应用名称或消息内容..."
              class="w-full px-6 py-3 rounded-full border-2 border-gray-300 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all text-gray-900 placeholder-gray-500"
            />
            <svg class="absolute right-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>
      </div>

      <!-- Scrollable Content Area -->
      <div
        class="flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 scrollbar-hide"
        @scroll="closeMenu"
      >
        <!-- Loading State -->
        <div v-if="loading" class="flex items-center justify-center py-12">
          <div class="text-center">
            <div class="inline-block animate-spin mb-4">
              <svg class="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
            <p class="text-gray-500">加载中...</p>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else-if="filteredConversations.length === 0" class="flex items-center justify-center py-12">
          <p class="text-gray-500 text-lg">暂无对话记录</p>
        </div>

        <!-- Conversations List -->
        <div v-else class="space-y-3 pb-8">
          <div
            v-for="conversation in filteredConversations"
            :key="conversation.id"
            :class="[
              'p-4 rounded-lg border transition-all bg-white cursor-pointer',
              conversation.source_type === 'assistant_agent'
                ? 'border-purple-200 hover:border-purple-400 hover:shadow-md'
                : 'border-gray-200 hover:border-blue-400 hover:shadow-md'
            ]"
            style="position: relative;"
            @click="changeConversation(conversation)"
          >
            <!-- 标题行 - 强制单行 -->
            <div class="mb-2 relative h-6 overflow-hidden">
              <div style="display: flex; align-items: center; height: 100%; white-space: nowrap; overflow: hidden; padding-right: 80px;">
                <h3 style="flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 1rem; font-weight: 600; color: #111827;">
                  {{ conversation.name }}
                </h3>
                <span v-if="conversation.source_type === 'assistant_agent' && conversation.agent_name" style="flex-shrink: 0; white-space: nowrap; margin-left: 4px; font-size: 0.75rem; padding: 4px 8px; border-radius: 4px; background-color: #ede9fe; color: #6d28d9;">
                  {{ conversation.agent_name }}
                </span>
              </div>
              <!-- 日期和菜单容器 - 固定宽度防止抖动 -->
              <div style="position: absolute; right: 0; top: 0; width: 80px; height: 24px; display: flex; align-items: center; justify-content: flex-end;">
                <!-- 日期 - 不hover时显示 -->
                <div v-show="visibleMenuId !== conversation.id" style="font-size: 0.75rem; color: #6b7280; white-space: nowrap;">
                  {{ formatDate(conversation.latest_message_at) }}
                </div>
                <!-- 菜单按钮 - hover时显示 -->
                <div v-show="visibleMenuId === conversation.id" style="display: flex;">
                  <a-dropdown :popup-visible="visibleMenuId === conversation.id" position="br" @click.stop @mousedown.stop>
                    <a-button
                      size="small"
                      type="text"
                      class="!text-gray-600 !bg-transparent !p-1"
                      @click.stop="visibleMenuId = visibleMenuId === conversation.id ? null : conversation.id"
                      @mousedown.stop
                    >
                      <template #icon>
                        <icon-more class="text-lg" />
                      </template>
                    </a-button>
                    <template #content>
                      <a-doption @click.stop="() => { openUpdateNameModal(conversation); visibleMenuId = null }">
                        <template #icon>
                          <icon-edit />
                        </template>
                        重命名
                      </a-doption>
                      <a-doption
                        class="text-red-700"
                        @click.stop="() => { deleteRecentConversation(conversation); visibleMenuId = null }"
                      >
                        <template #icon>
                          <icon-delete />
                        </template>
                        删除会话
                      </a-doption>
                    </template>
                  </a-dropdown>
                </div>
              </div>
            </div>

            <!-- 鼠标悬停时显示菜单 -->
            <div @mouseenter="visibleMenuId = conversation.id" @mouseleave="visibleMenuId = null" style="position: absolute; top: 0; right: 0; width: 80px; height: 24px;"></div>

            <!-- 应用标签 -->
            <div v-if="conversation.app_name" class="mb-2">
              <span class="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700 whitespace-nowrap inline-block">
                {{ conversation.app_name }}
              </span>
            </div>

            <!-- 消息预览 -->
            <div v-if="conversation.human_message || conversation.ai_message" class="space-y-1">
              <div v-if="conversation.human_message" class="text-sm text-gray-700 line-clamp-1">
                <span class="font-medium text-gray-600">Q:</span>
                <span>{{ truncateText(String(conversation.human_message || ''), 100) }}</span>
              </div>
              <div v-if="conversation.ai_message" class="text-sm text-gray-700 line-clamp-1">
                <span class="font-medium text-gray-600">A:</span>
                <span>{{ truncateText(String(conversation.ai_message || ''), 100) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Name Modal -->
    <update-conversation-name-modal
      v-model:visible="updateConversationNameVisible"
      :conversation_id="updateConversationNameId"
      :conversation_name="updateConversationName"
      @saved="updateConversationNameSuccess"
    />
  </div>
</template>

<style scoped>
/* 防止背景闪动 */
:deep(.absolute.inset-0.z-0.pointer-events-none) {
  will-change: auto;
  transform: translateZ(0);
  backface-visibility: hidden;
}

:deep(mark) {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.3), rgba(139, 92, 246, 0.3));
  padding: 0 2px;
  border-radius: 2px;
  font-weight: 600;
  color: inherit;
}

/* 渐变色文字高亮 */
:deep(.gradient-highlight) {
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  font-weight: 600;
}

/* 隐藏所有滚条 */
html, body {
  overflow: hidden;
}

/* 隐藏滚条 - 适用于 scrollbar-hide 类 */
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* Arco Design 菜单项样式 */
:deep(.arco-dropdown-option) {
  padding: 8px 12px !important;
  font-size: 14px !important;
  transition: all 0.2s ease !important;
}

:deep(.arco-dropdown-option:hover) {
  background-color: #f5f5f5 !important;
}

:deep(.arco-dropdown-divider) {
  margin: 4px 0 !important;
}

/* 对话名称截断样式 */
h3 {
  min-width: 0;
  flex-shrink: 1;
}

:deep(.arco-dropdown-divider) {
  margin: 4px 0 !important;
}
</style>
