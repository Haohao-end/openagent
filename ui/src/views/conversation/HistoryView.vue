<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ScrollNavigator from '@/components/ScrollNavigation/ScrollNavigator.vue'
import { useGetRecentConversations, useDeleteConversation } from '@/hooks/use-conversation'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import type { RecentConversation } from '@/models/conversation'
import UpdateConversationNameModal from '@/views/layouts/components/UpdateConversationNameModal.vue'

const router = useRouter()
const searchQuery = ref('')
const selectedIds = ref(new Set<string>())
const hoveredConversationId = ref<string | null>(null)

// 编辑名称相关
const updateConversationNameVisible = ref(false)
const updateConversationNameId = ref('')
const updateConversationName = ref('')

const {
  loading: getRecentConversationsLoading,
  conversations: allConversations,
  loadRecentConversations: loadRecentConversationsHook,
} = useGetRecentConversations()

const { handleDeleteConversation } = useDeleteConversation()

// 加载所有对话
const loadConversations = async () => {
  await loadRecentConversationsHook(1000)
}

// 搜索过滤
const filteredConversations = computed(() => {
  if (!searchQuery.value.trim()) {
    return allConversations.value
  }

  const query = searchQuery.value.toLowerCase()
  return allConversations.value.filter((conv) => {
    const nameMatch = conv.name.toLowerCase().includes(query)
    const messageMatch = (conv.human_message || '').toLowerCase().includes(query) ||
                        (conv.ai_message || '').toLowerCase().includes(query)
    return nameMatch || messageMatch
  })
})

// 格式化日期
const formatDate = (timestamp: number | string) => {
  const date = new Date(typeof timestamp === 'string' ? parseInt(timestamp) * 1000 : timestamp * 1000)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  const dateStr = date.toLocaleDateString('zh-CN')
  const todayStr = today.toLocaleDateString('zh-CN')
  const yesterdayStr = yesterday.toLocaleDateString('zh-CN')

  if (dateStr === todayStr) return '今天'
  if (dateStr === yesterdayStr) return '昨天'
  return dateStr
}

// 高亮搜索词
const highlightText = (text: string) => {
  if (!searchQuery.value.trim()) return text
  const query = searchQuery.value
  const regex = new RegExp(`(${query})`, 'gi')
  return text.replace(regex, '<mark>$1</mark>')
}

const truncateText = (text: string, maxLength: number = 20) => {
  if (!text) return text
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text
}

// 删除单个对话（显示浏览器提示）
const deleteConversation = (conversation: RecentConversation) => {
  handleDeleteConversation(conversation.id, async () => {
    const idx = allConversations.value.findIndex((item) => item.id === conversation.id)
    if (idx !== -1) {
      allConversations.value.splice(idx, 1)
    }
  })
}

// 打开编辑名称模态窗
const openUpdateNameModal = (conversation: RecentConversation) => {
  updateConversationNameId.value = conversation.id
  updateConversationName.value = conversation.name
  updateConversationNameVisible.value = true
}

// 编辑名称成功回调
const updateConversationNameSuccess = (conversation_id: string, name: string) => {
  const idx = allConversations.value.findIndex((item) => item.id === conversation_id)
  if (idx !== -1) {
    allConversations.value[idx].name = name
  }
}

// 跳转到对话
const goToConversation = (conversation: RecentConversation) => {
  if (conversation.source_type === 'assistant_agent') {
    router.push({
      path: '/home',
      query: { conversation_id: conversation.id },
    })
  } else if (conversation.source_type === 'public_app' && conversation.app_id) {
    router.push({
      path: `/store/public-apps/${conversation.app_id}/preview`,
      query: {
        conversation_id: conversation.id,
        message_id: conversation.message_id,
      },
    })
  } else if (conversation.source_type === 'app_debugger' && conversation.app_id) {
    router.push({
      path: `/space/apps/${conversation.app_id}`,
      query: {
        conversation_id: conversation.id,
        message_id: conversation.message_id,
      },
    })
  }
}

// 初始化加载
loadConversations()

// 监听搜索词变化
watch(
  () => searchQuery.value,
  () => {
    selectedIds.value.clear()
  },
)
</script>

<template>
  <scroll-navigator>
    <div class="h-full flex flex-col bg-white overflow-hidden">
    <!-- 头部 -->
    <div class="border-b border-gray-200 p-6 flex-shrink-0">
      <h1 class="text-2xl font-bold text-gray-900 mb-4">对话历史</h1>
      <div class="flex gap-3">
        <a-input-search
          v-model="searchQuery"
          placeholder="搜索对话名称或消息内容..."
          allow-clear
          class="flex-1"
          size="large"
        />
      </div>
    </div>

    <!-- 内容区域 - 只有这里滚动 -->
    <div class="flex-1 min-h-0 overflow-y-auto p-6">
      <a-skeleton v-if="getRecentConversationsLoading" :loading="true" animation>
        <a-skeleton-line :rows="5" :line-height="120" :line-spacing="16" />
      </a-skeleton>

      <div v-else-if="filteredConversations.length === 0" class="text-center py-12">
        <div class="text-gray-400 text-lg">
          {{ searchQuery ? '没有找到匹配的对话' : '暂无对话历史' }}
        </div>
      </div>

      <div v-else class="grid gap-8">
        <!-- 对话卡片列表 -->
        <div
          v-for="conversation in filteredConversations"
          :key="conversation.id"
          data-scroll-item
          class="group relative border border-gray-200 rounded-2xl p-8 min-h-[220px] hover:border-blue-300 hover:shadow-lg transition-all bg-white"
          @mouseenter="hoveredConversationId = conversation.id"
          @mouseleave="hoveredConversationId = null"
        >
          <!-- 内容 -->
          <div class="h-full flex flex-col justify-between">
            <!-- 标题和日期 -->
            <div class="flex items-start justify-between gap-4 mb-8">
              <h3
                class="text-lg font-semibold text-gray-900 flex-1 min-w-0 truncate cursor-pointer hover:text-blue-600 pr-4"
                :title="conversation.name"
                @click="goToConversation(conversation)"
              >
                {{ truncateText(conversation.name, 20) }}
              </h3>
              <div class="flex items-center gap-2 flex-shrink-0 self-start pl-2">
                <!-- 时间显示 - 未hover时显示 -->
                <span
                  v-if="hoveredConversationId !== conversation.id"
                  class="text-sm text-gray-500 whitespace-nowrap pt-1"
                >
                  {{ formatDate(conversation.created_at) }}
                </span>
                <!-- 菜单按钮 - hover时显示 -->
                <a-dropdown
                  v-else
                  position="br"
                  @click.stop
                >
                  <a-button
                    size="mini"
                    type="text"
                    class="!text-gray-400 !bg-transparent"
                  >
                    <template #icon>
                      <icon-more />
                    </template>
                  </a-button>
                  <template #content>
                    <a-doption @click.stop="() => openUpdateNameModal(conversation)">
                      <template #icon>
                        <icon-edit />
                      </template>
                      重命名
                    </a-doption>
                    <a-doption
                      class="text-red-700"
                      @click.stop="() => deleteConversation(conversation)"
                    >
                      <template #icon>
                        <icon-delete />
                      </template>
                      删除
                    </a-doption>
                  </template>
                </a-dropdown>
              </div>
            </div>

            <!-- 消息预览 -->
            <div class="space-y-6 cursor-pointer" @click="goToConversation(conversation)">
              <!-- 人类消息 -->
              <div v-if="conversation.human_message" class="flex gap-4">
                <span class="text-sm font-medium text-gray-500 flex-shrink-0 leading-7">用户:</span>
                <div
                  class="text-sm text-gray-700 line-clamp-2 flex-1 leading-7"
                  v-html="highlightText(conversation.human_message)"
                />
              </div>

              <!-- AI 消息 -->
              <div v-if="conversation.ai_message" class="flex gap-4">
                <span class="text-sm font-medium text-gray-500 flex-shrink-0 leading-7">AI:</span>
                <div
                  class="text-sm text-gray-700 line-clamp-3 flex-1 leading-7"
                  v-html="highlightText(conversation.ai_message)"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑名称模态窗 -->
    <update-conversation-name-modal
      :visible="updateConversationNameVisible"
      :conversation_id="updateConversationNameId"
      :conversation_name="updateConversationName"
      @update:visible="updateConversationNameVisible = $event"
      @saved="updateConversationNameSuccess"
    />
  </div>
  </scroll-navigator>
</template>

<style scoped>
:deep(mark) {
  background-color: #ffd666;
  color: inherit;
  font-weight: 500;
  padding: 0 2px;
  border-radius: 2px;
}

/* 隐藏滚条 */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
