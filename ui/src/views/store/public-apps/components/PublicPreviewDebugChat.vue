<script setup lang="ts">
import ChatComposer from '@/components/ChatComposer.vue'
import ChatConversationSkeleton from '@/components/skeletons/ChatConversationSkeleton.vue'
import ChatMessageTimeline from '@/components/chat/ChatMessageTimeline.vue'
import { useAudioToText } from '@/hooks/use-audio'
import { useChatImageUpload } from '@/hooks/use-chat-image-upload'
import { useChatQueryInput } from '@/hooks/use-chat-query-input'
import {
  getPublicAppA2aConversationMessages,
  sendPublicAppA2aMessage,
} from '@/services/public-app'
import { uploadImage } from '@/services/upload-file'
import { useAccountStore } from '@/stores/account'
import { Message } from '@arco-design/web-vue'
import { computed, nextTick, onMounted, ref, watch, type PropType } from 'vue'
import { useRoute } from 'vue-router'
import {
  applyChatStreamEvent,
  type StreamEventResponse,
  type StreamMessage,
  type StreamState,
} from '@/views/shared/chat-stream'

const route = useRoute()
const PUBLIC_APP_DEBUG_QUERY_DRAFT_STORAGE_KEY_PREFIX = 'draft:public-apps:debug-query'
const PUBLIC_APP_CONTEXT_STORAGE_KEY_PREFIX = 'public-apps:debug-context'
const props = defineProps({
  app: { type: Object, default: () => ({}), required: true },
  suggested_after_answer: {
    type: Object as PropType<{ enable: boolean }>,
    default: () => ({ enable: true }),
    required: true,
  },
  opening_statement: { type: String, default: '', required: true },
  opening_questions: { type: Array as PropType<string[]>, default: () => [], required: true },
  text_to_speech: {
    type: Object,
    default: () => ({ enable: true, auto_play: true, voice: 'alex' }),
    required: false,
  },
})

const { query, queryTextareaRef, adjustQueryTextareaHeight } = useChatQueryInput({
  getDraftKey: () => `${PUBLIC_APP_DEBUG_QUERY_DRAFT_STORAGE_KEY_PREFIX}:${String(route.params?.app_id ?? '')}`,
  minHeight: 32,
  maxHeight: 96,
})

type PublicStreamMessage = StreamMessage & {
  query: string
  image_urls: string[]
  suggested_questions: string[]
}

const messages = ref<PublicStreamMessage[]>([])
const loading = ref(false)
const image_urls = ref<string[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const uploadFileLoading = ref(false)
const isRecording = ref(false)
const chatContextId = ref('')
const accountStore = useAccountStore()
const activeAccount = computed(() => ({
  name:
    String(accountStore.account?.name || '').trim() ||
    String(accountStore.account?.email || '').split('@')[0] ||
    '',
  avatar: String(accountStore.account?.avatar || '').trim(),
}))
const { loading: audioToTextLoading } = useAudioToText()
const timelineRef = ref<{ scrollToBottom?: () => void } | null>(null)

const getContextStorageKey = () =>
  `${PUBLIC_APP_CONTEXT_STORAGE_KEY_PREFIX}:${String(route.params?.app_id ?? '')}:${String(accountStore.account?.id ?? 'anonymous')}`

const restoreContextId = () => {
  if (typeof window === 'undefined') return ''
  return String(window.localStorage.getItem(getContextStorageKey()) || '').trim()
}

const saveContextId = (value: string) => {
  if (typeof window === 'undefined') return
  if (value.trim()) {
    window.localStorage.setItem(getContextStorageKey(), value.trim())
    return
  }
  window.localStorage.removeItem(getContextStorageKey())
}

const setQueryTextareaRef = (element: HTMLTextAreaElement | null) => {
  queryTextareaRef.value = element
}
const setFileInputRef = (element: HTMLInputElement | null) => {
  fileInput.value = element
}

const { triggerFileInput, handleFileChange } = useChatImageUpload({
  imageUrls: image_urls,
  uploadFileLoading,
  fileInput,
  uploadImage,
  onError: (message) => Message.error(message),
  onSuccess: (message) => Message.success(message),
})

const createStreamMessage = (queryText: string): PublicStreamMessage => ({
  id: `tmp-${Date.now()}`,
  conversation_id: chatContextId.value,
  answer: '',
  latency: 0,
  total_token_count: 0,
  agent_thoughts: [],
  query: queryText,
  image_urls: [...image_urls.value],
  suggested_questions: [],
})

const clearConversation = () => {
  messages.value = []
  chatContextId.value = ''
  saveContextId('')
  image_urls.value = []
  query.value = ''
  void nextTick(() => timelineRef.value?.scrollToBottom?.())
}

const loadPublicConversationMessages = async (conversationId: string) => {
  if (!conversationId) return
  const res = await getPublicAppA2aConversationMessages(String(route.params?.app_id), conversationId)
  const history = [...(res.data || [])].reverse()
  messages.value = history.map((item) => ({
    id: item.id,
    conversation_id: item.conversation_id,
    answer: item.answer || '',
    latency: Number(item.latency || 0),
    total_token_count: Number(item.total_token_count || 0),
    agent_thoughts: [],
    query: item.query || '',
    image_urls: item.image_urls || [],
    suggested_questions: item.suggested_questions || [],
  }))
}

const loadConversationFromRoute = async () => {
  const routeConversationId = String(route.query.conversation_id || '').trim()
  if (routeConversationId) {
    chatContextId.value = routeConversationId
    saveContextId(routeConversationId)
    await loadPublicConversationMessages(routeConversationId)
    return
  }

  const restoredContextId = restoreContextId()
  if (restoredContextId) {
    chatContextId.value = restoredContextId
    await loadPublicConversationMessages(restoredContextId)
  }
}

const handleSubmitQuestion = async (question: string) => {
  query.value = question
  await handleSubmit()
}

const handleSubmit = async () => {
  const currentQuery = query.value.trim()
  if (!currentQuery) {
    Message.warning('用户提问不能为空')
    return
  }

  const currentMessage = createStreamMessage(currentQuery)
  messages.value.unshift(currentMessage)
  await nextTick()
  const streamState: StreamState = {
    position: 0,
    message_id: '',
    task_id: '',
    conversation_id: chatContextId.value,
  }
  query.value = ''
  loading.value = true
  try {
    await sendPublicAppA2aMessage(String(route.params?.app_id), currentQuery, chatContextId.value, (eventResponse) => {
      const streamResult = applyChatStreamEvent(
        currentMessage,
        eventResponse as StreamEventResponse,
        streamState,
      )
      streamState.position = streamResult.state.position
      streamState.message_id = streamResult.state.message_id
      streamState.task_id = streamResult.state.task_id
      streamState.conversation_id = streamResult.state.conversation_id
      if (streamState.conversation_id) {
        chatContextId.value = streamState.conversation_id
        saveContextId(streamState.conversation_id)
      }
      void timelineRef.value?.scrollToBottom?.()
    })
  } catch (error: unknown) {
    Message.error(error instanceof Error ? error.message : '发送消息失败')
  } finally {
    loading.value = false
  }
}

const handleQueryKeydown = (event: KeyboardEvent) => {
  const isSubmitShortcut =
    event.key === 'Enter' &&
    !event.shiftKey &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.altKey &&
    !event.isComposing
  if (!isSubmitShortcut) return
  event.preventDefault()
  void handleSubmit()
}

watch(query, () => adjustQueryTextareaHeight())

onMounted(async () => {
  await loadConversationFromRoute()
})

watch(
  () => [String(route.params?.app_id ?? ''), String(route.query.conversation_id ?? '')],
  async ([appId, conversationId], [prevAppId, prevConversationId]) => {
    if (appId === prevAppId && conversationId === prevConversationId) return
    messages.value = []
    chatContextId.value = ''
    await loadConversationFromRoute()
    void timelineRef.value?.scrollToBottom?.()
  },
)
</script>

<template>
  <div class="h-full min-h-0 flex flex-col overflow-hidden">
    <div class="flex-1 min-h-0 flex flex-col overflow-hidden">
      <div
        v-if="loading && messages.length === 0"
        class="flex-1 min-h-0 px-6 pt-6 overflow-hidden"
      >
        <chat-conversation-skeleton :pair-count="6" />
      </div>
      <div v-else-if="messages.length > 0" class="flex-1 min-h-0 overflow-hidden flex flex-col px-6">
        <chat-message-timeline
          ref="timelineRef"
          class="flex-1 min-h-0"
          :messages="messages"
          :account="activeAccount"
          :app="props.app"
          :loading="loading"
          :text-to-speech-enable="props.text_to_speech.enable"
        />
      </div>
      <div
        v-else
        class="flex-1 min-h-0 flex flex-col p-6 gap-2 items-center justify-center overflow-hidden"
      >
        <div class="flex flex-col items-center gap-2">
          <a-avatar :size="48" shape="square" class="rounded-lg" :image-url="props.app?.icon" />
          <div class="text-lg text-gray-700">{{ props.app?.name }}</div>
        </div>
        <div v-if="props.opening_statement" class="bg-gray-100 w-full px-4 py-3 rounded-lg text-gray-700">
          {{ props.opening_statement }}
        </div>
        <div class="flex flex-col items-start gap-2 w-full">
          <div
            v-for="(opening_question, idx) in props.opening_questions.filter((item) => item.trim() !== '')"
            :key="idx"
            class="w-fit max-w-full px-4 py-1.5 border rounded-lg text-gray-700 cursor-pointer hover:bg-gray-50 break-words"
            @click="async () => await handleSubmitQuestion(opening_question)"
          >
            {{ opening_question }}
          </div>
        </div>
      </div>
      <div class="w-full flex flex-col flex-shrink-0 border-t bg-white">
        <div class="px-6 pt-4">
          <chat-composer
            v-model="query"
            size="compact"
            :textarea-ref-setter="setQueryTextareaRef"
            :file-input-ref-setter="setFileInputRef"
            :image-urls="image_urls"
            :show-image-previews="true"
            :show-clear-button="true"
            :clear-disabled="messages.length === 0 && !chatContextId"
            :clear-loading="false"
            :upload-loading="uploadFileLoading"
            :submit-loading="loading"
            :audio-to-text-loading="audioToTextLoading"
            :is-recording="isRecording"
            clear-title="清空调试会话"
            placeholder="发送调试消息"
            @clear="clearConversation"
            @upload="triggerFileInput"
            @file-change="(event) => handleFileChange(event)"
            @input="() => adjustQueryTextareaHeight()"
            @keydown="(event) => handleQueryKeydown(event)"
            @remove-image="(index) => { image_urls.splice(index, 1) }"
            @start-record="() => {}"
            @stop-record="() => {}"
            @submit="handleSubmit"
          />
        </div>
        <div class="text-center text-gray-500 text-xs py-4">
          内容由AI生成，无法确保真实准确，仅供参考
        </div>
      </div>
    </div>
  </div>
</template>
