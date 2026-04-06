<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import AiDynamicBackground from '@/components/AiDynamicBackground.vue'
import { OPEN_AGENT_NAME } from '@/config/openagent'
import { useMarkdownRenderer } from '@/hooks/use-markdown-renderer'
import { searchConversations } from '@/services/conversation-search'
import { useGetRecentConversations, useDeleteConversation } from '@/hooks/use-conversation'
import UpdateConversationNameModal from '@/views/layouts/components/UpdateConversationNameModal.vue'
import type { SearchConversation, SearchMatchField } from '@/services/conversation-search'
import type { RecentConversation } from '@/models/conversation'
import 'github-markdown-css'
import 'highlight.js/styles/github.css'

type SearchableConversation = RecentConversation | SearchConversation

const router = useRouter()
const pageRef = ref<HTMLElement | null>(null)
const scrollAreaRef = ref<HTMLElement | null>(null)
const { renderMarkdown } = useMarkdownRenderer()

// State
const searchQuery = ref('')
const conversations = ref<SearchConversation[]>([])
const loading = ref(false)
const updateConversationNameVisible = ref(false)
const updateConversationNameId = ref('')
const updateConversationName = ref('')
const hoveredMenuId = ref<string | null>(null)
const openMenuId = ref<string | null>(null)

// 最近对话
const {
  conversations: recentConversations,
  loadRecentConversations: loadRecentConversationsHook,
} = useGetRecentConversations()

const { handleDeleteConversation } = useDeleteConversation()

// 关闭菜单
const closeMenu = () => {
  openMenuId.value = null
}

const handleCardMouseEnter = (conversationId: string) => {
  hoveredMenuId.value = conversationId
}

const handleCardMouseLeave = (conversationId: string) => {
  if (hoveredMenuId.value === conversationId) {
    hoveredMenuId.value = null
  }
}

const isMenuIconVisible = (conversationId: string) => {
  return hoveredMenuId.value === conversationId || openMenuId.value === conversationId
}

const toggleConversationMenu = (conversationId: string) => {
  openMenuId.value = openMenuId.value === conversationId ? null : conversationId
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
  openMenuId.value = null
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
  openMenuId.value = null
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

const escapeHtml = (text: string) => {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const escapeRegExp = (text: string) => {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

const highlightText = (text: string) => {
  const safeText = escapeHtml(text || '')
  const keyword = searchQuery.value.trim()
  if (!keyword) return safeText

  const safeKeyword = escapeRegExp(keyword)
  const regex = new RegExp(`(${safeKeyword})`, 'gi')
  return safeText.replace(regex, '<span class="gradient-highlight">$1</span>')
}

const truncateText = (text: string, maxLength: number = 100) => {
  if (!text) return ''

  const normalizedText = String(text).replace(/\s+/g, ' ').trim()
  if (!normalizedText) return ''

  const keyword = searchQuery.value.trim().toLowerCase()
  if (!keyword) {
    return normalizedText.length > maxLength
      ? `${normalizedText.substring(0, maxLength)}...`
      : normalizedText
  }

  const keywordIndex = normalizedText.toLowerCase().indexOf(keyword)
  if (keywordIndex === -1) {
    return normalizedText.length > maxLength
      ? `${normalizedText.substring(0, maxLength)}...`
      : normalizedText
  }

  const windowSize = Math.max(maxLength, keyword.length)
  let start = Math.max(0, keywordIndex - Math.floor((windowSize - keyword.length) / 2))
  let end = Math.min(normalizedText.length, start + windowSize)

  if (end - start < windowSize) {
    start = Math.max(0, end - windowSize)
  }

  const snippet = normalizedText.substring(start, end)
  return `${start > 0 ? '...' : ''}${snippet}${end < normalizedText.length ? '...' : ''}`
}

const highlightAndTruncateText = (text: string, maxLength: number =100) => {
 return highlightText(truncateText(text, maxLength))
}

const highlightRenderedHtml = (html: string) => {
  const keyword = searchQuery.value.trim()
  if (!keyword || !html || typeof document === 'undefined') return html

  const template = document.createElement('template')
  template.innerHTML = html
  const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_TEXT)
  const textNodes: Text[] = []

  let currentNode = walker.nextNode()
  while (currentNode) {
    textNodes.push(currentNode as Text)
    currentNode = walker.nextNode()
  }

  const regex = new RegExp(escapeRegExp(keyword), 'gi')
  for (const textNode of textNodes) {
    const textContent = textNode.textContent || ''
    const parentElement = textNode.parentElement

    if (!parentElement || !textContent.trim()) continue
    if (parentElement.closest('.md-code-copy-btn')) continue

    regex.lastIndex = 0
    if (!regex.test(textContent)) continue

    const fragment = document.createDocumentFragment()
    let lastIndex = 0
    regex.lastIndex = 0

    let match: RegExpExecArray | null
    while ((match = regex.exec(textContent))) {
      if (match.index > lastIndex) {
        fragment.appendChild(document.createTextNode(textContent.slice(lastIndex, match.index)))
      }

      const highlightNode = document.createElement('span')
      highlightNode.className = 'gradient-highlight'
      highlightNode.textContent = match[0]
      fragment.appendChild(highlightNode)

      lastIndex = match.index + match[0].length
    }

    if (lastIndex < textContent.length) {
      fragment.appendChild(document.createTextNode(textContent.slice(lastIndex)))
    }

    textNode.parentNode?.replaceChild(fragment, textNode)
  }

  return template.innerHTML
}

const renderMessagePreview = (conversation: SearchableConversation, field: 'human_message' | 'ai_message') => {
  const content = String(conversation[field] || '')
  if (!content) return ''

  return highlightRenderedHtml(renderMarkdown(content))
}

const getMatchedFields = (conversation: SearchableConversation): SearchMatchField[] => {
  if ('matched_fields' in conversation && Array.isArray(conversation.matched_fields)) {
    return conversation.matched_fields
  }

  return []
}

const hasMatchedField = (conversation: SearchableConversation, field: SearchMatchField) => {
  return getMatchedFields(conversation).includes(field)
}

const getNonMessageMatchLabels = (conversation: SearchableConversation) => {
  const labels: string[] = []

  if (hasMatchedField(conversation, 'name')) {
    labels.push('标题')
  }

  if (hasMatchedField(conversation, 'app_name')) {
    labels.push('应用')
  }

  if (hasMatchedField(conversation, 'agent_name')) {
    labels.push(OPEN_AGENT_NAME)
  }

  return labels
}

const hasMessageKeywordMatch = (conversation: SearchableConversation) => {
  return hasMatchedField(conversation, 'human_message') || hasMatchedField(conversation, 'ai_message')
}

const shouldShowMessageField = (conversation: SearchableConversation, field: 'human_message' | 'ai_message') => {
  if (!conversation[field]) return false
  if (!searchQuery.value.trim()) return true

  const matchedFields = getMatchedFields(conversation)
  if (matchedFields.length === 0) return true

  return matchedFields.includes(field)
}

const truncateConversationName = (name: string, hasAgent: boolean) => {
  // 如果有agent名称，对话名称最多保留30个字符，否则保留50个字符
  const maxLength = hasAgent ? 30 : 50
  if (name.length > maxLength) {
    return name.substring(0, maxLength) + '...'
  }
  return name
}

const changeConversation = async (conversation: SearchableConversation) => {
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

const canScrollWithDelta = (element: HTMLElement, deltaY: number) => {
 if (deltaY ===0) return false
 if (element.scrollHeight <= element.clientHeight) return false
 if (deltaY <0) return element.scrollTop >0
 return element.scrollTop + element.clientHeight < element.scrollHeight
}

const handlePageWheel = (event: WheelEvent) => {
 const pageElement = pageRef.value
 const scrollElement = scrollAreaRef.value

 if (!pageElement || !scrollElement) return
 if (event.target !== pageElement) return
 if (!canScrollWithDelta(scrollElement, event.deltaY)) return

 event.preventDefault()
 scrollElement.scrollTop += event.deltaY
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
 ref="pageRef"
 data-testid="conversation-search-page"
    class="relative w-full h-screen overflow-hidden flex flex-col"
    style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 25%, #f3e8ff 50%, #fce7f3 75%, #f0f9ff 100%);"
    @click="closeMenu"
    @wheel="handlePageWheel"
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
              data-testid="conversation-search-input"
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
        ref="scrollAreaRef"
        data-testid="conversation-search-scroll-area"
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
            data-testid="conversation-card"
            :class="[
              'px-3 py-2.5 min-h-[108px] overflow-hidden rounded-lg border transition-all bg-white cursor-pointer flex flex-col',
              conversation.source_type === 'assistant_agent'
                ? 'border-purple-200 hover:border-purple-400 hover:shadow-md'
                : 'border-gray-200 hover:border-blue-400 hover:shadow-md'
            ]"
            style="position: relative;"
            @click="changeConversation(conversation)"
            @mouseenter="handleCardMouseEnter(conversation.id)"
            @mouseleave="handleCardMouseLeave(conversation.id)"
          >
            <!-- 标题行 - 强制单行 -->
            <div class="mb-0.5 relative h-6 overflow-hidden">
              <div style="display: flex; align-items: center; height: 100%; white-space: nowrap; overflow: hidden; padding-right: 80px;">
                <h3
                  style="flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 1rem; font-weight: 600; color: #111827;"
                  v-html="highlightAndTruncateText(conversation.name, conversation.source_type === 'assistant_agent' && conversation.agent_name ? 30 : 50)"
                />
                <span
                  v-if="conversation.source_type === 'assistant_agent' && conversation.agent_name"
                  style="flex-shrink: 0; white-space: nowrap; margin-left: 4px; font-size: 0.75rem; padding: 4px 8px; border-radius: 4px; background-color: #ede9fe; color: #6d28d9;"
                  v-html="highlightText(conversation.agent_name)"
                />
              </div>
              <!-- 日期和菜单容器 - 固定宽度防止抖动 -->
              <div style="position: absolute; right: 0; top: 0; width: 80px; height: 24px; display: flex; align-items: center; justify-content: flex-end;">
                <!-- 日期 - 不hover时显示 -->
                <div v-show="!isMenuIconVisible(conversation.id)" style="font-size: 0.75rem; color: #6b7280; white-space: nowrap;">
                  {{ formatDate(conversation.latest_message_at) }}
                </div>
                <!-- 菜单按钮 - hover时显示 -->
                <div v-show="isMenuIconVisible(conversation.id)" style="display: flex;">
                  <a-dropdown :popup-visible="openMenuId === conversation.id" position="br" @click.stop @mousedown.stop>
                    <a-button
                      size="small"
                      type="text"
                      class="!text-gray-600 !bg-transparent !p-1"
                      @click.stop="toggleConversationMenu(conversation.id)"
                      @mousedown.stop
                    >
                      <template #icon>
                        <icon-more class="text-lg" />
                      </template>
                    </a-button>
                    <template #content>
                      <a-doption @click.stop="() => { openUpdateNameModal(conversation); openMenuId = null }">
                        <template #icon>
                          <icon-edit />
                        </template>
                        重命名
                      </a-doption>
                      <a-doption
                        class="text-red-700"
                        @click.stop="() => { deleteRecentConversation(conversation); openMenuId = null }"
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
            <!-- 应用标签 -->
            <div v-if="conversation.app_name" class="mb-0.5">
              <span
                class="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700 whitespace-nowrap inline-block"
                v-html="highlightText(conversation.app_name)"
              />
            </div>

            <div
              v-if="searchQuery.trim() && !hasMessageKeywordMatch(conversation) && getNonMessageMatchLabels(conversation).length > 0"
              class="mb-0.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1"
            >
              关键词命中{{ getNonMessageMatchLabels(conversation).join(' / ') }}，当前卡片没有命中消息正文
            </div>

            <!-- 消息预览 -->
            <div
              v-if="shouldShowMessageField(conversation, 'human_message') || shouldShowMessageField(conversation, 'ai_message')"
              class="space-y-0.5 min-h-0 overflow-hidden"
            >
              <div v-if="shouldShowMessageField(conversation, 'human_message')" class="search-message-row">
                <span class="search-message-prefix">Q:</span>
                <div
                  class="search-markdown-preview markdown-body"
                  v-html="renderMessagePreview(conversation, 'human_message')"
                />
              </div>
              <div v-if="shouldShowMessageField(conversation, 'ai_message')" class="search-message-row">
                <span class="search-message-prefix">A:</span>
                <div
                  class="search-markdown-preview markdown-body"
                  v-html="renderMessagePreview(conversation, 'ai_message')"
                />
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

:deep(.search-message-row) {
  display: flex;
  gap: 4px;
  align-items: flex-start;
  min-height: 0;
}

:deep(.search-message-prefix) {
  flex-shrink: 0;
  font-size: 0.75rem;
  font-weight: 600;
  color: #4b5563;
  line-height: 1.3;
}

:deep(.search-markdown-preview.markdown-body) {
  flex: 1;
  min-width: 0;
  max-height: 2.05rem;
  overflow: hidden;
  padding: 0;
  background: transparent;
  color: #374151;
  font-size: 0.75rem;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  white-space: normal;
  word-break: break-word;
}

:deep(.search-markdown-preview.markdown-body > :first-child) {
  margin-top: 0;
}

:deep(.search-markdown-preview.markdown-body > :last-child) {
  margin-bottom: 0;
}

:deep(.search-markdown-preview.markdown-body p),
:deep(.search-markdown-preview.markdown-body ul),
:deep(.search-markdown-preview.markdown-body ol),
:deep(.search-markdown-preview.markdown-body li),
:deep(.search-markdown-preview.markdown-body h1),
:deep(.search-markdown-preview.markdown-body h2),
:deep(.search-markdown-preview.markdown-body h3),
:deep(.search-markdown-preview.markdown-body h4),
:deep(.search-markdown-preview.markdown-body h5),
:deep(.search-markdown-preview.markdown-body h6),
:deep(.search-markdown-preview.markdown-body pre),
:deep(.search-markdown-preview.markdown-body blockquote),
:deep(.search-markdown-preview.markdown-body code),
:deep(.search-markdown-preview.markdown-body table),
:deep(.search-markdown-preview.markdown-body thead),
:deep(.search-markdown-preview.markdown-body tbody),
:deep(.search-markdown-preview.markdown-body tr),
:deep(.search-markdown-preview.markdown-body th),
:deep(.search-markdown-preview.markdown-body td) {
  display: inline;
  margin: 0;
  padding: 0;
  border: 0;
  font-size: inherit !important;
  line-height: inherit !important;
  background: transparent;
}

:deep(.search-markdown-preview.markdown-body h1),
:deep(.search-markdown-preview.markdown-body h2),
:deep(.search-markdown-preview.markdown-body h3),
:deep(.search-markdown-preview.markdown-body h4),
:deep(.search-markdown-preview.markdown-body h5),
:deep(.search-markdown-preview.markdown-body h6) {
  font-weight: 600;
}

:deep(.search-markdown-preview .md-code-block) {
  display: inline;
  margin: 0;
  border: 0;
  background: transparent;
}

:deep(.search-markdown-preview .md-code-header) {
  display: none;
}

:deep(.search-markdown-preview.markdown-body pre) {
  white-space: pre-wrap;
}

:deep(.arco-dropdown-divider) {
  margin: 4px 0 !important;
}
</style>
