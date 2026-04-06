<script setup lang="ts">
import AiMessage from '@/components/AiMessage.vue'
import ChatComposer from '@/components/ChatComposer.vue'
import HumanMessage from '@/components/HumanMessage.vue'
import ScrollNavigator from '@/components/ScrollNavigation/ScrollNavigator.vue'
import ChatConversationSkeleton from '@/components/skeletons/ChatConversationSkeleton.vue'
import { useGenerateSuggestedQuestions } from '@/hooks/use-ai'
import { useChatImageUpload } from '@/hooks/use-chat-image-upload'
import { useChatQueryInput } from '@/hooks/use-chat-query-input'
import {
  useDebugChat,
  useDeleteDebugConversation,
  useGetDebugConversationMessagesWithPage,
  useStopDebugChat,
} from '@/hooks/use-app'
import { useAudioPlayer, useAudioToText } from '@/hooks/use-audio'
import { uploadImage } from '@/services/upload-file'
import { useAccountStore } from '@/stores/account'
import { getErrorMessage } from '@/utils/error'
import { Message } from '@arco-design/web-vue'
import AudioRecorder from 'js-audio-recorder'
import { nextTick, onMounted, onUnmounted, type PropType, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import {
  applyChatStreamEvent,
  type StreamMessage,
  type StreamState,
} from '@/views/shared/chat-stream'
import { normalizeMessageMetrics, type MessageMetrics } from '@/views/shared/chat-metrics'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'

// 1.定义自定义组件所需数据
const route = useRoute()
const router = useRouter()
const SPACE_APP_DEBUG_QUERY_DRAFT_STORAGE_KEY_PREFIX = 'draft:space-apps:debug-query'
const props = defineProps({
  app: {
    type: Object,
    default: () => {
      return {}
    },
    required: true,
  },
  suggested_after_answer: {
    type: Object as PropType<{ enable: boolean }>,
    default: () => {
      return { enable: true }
    },
    required: true,
  },
  opening_statement: { type: String, default: '', required: true },
  opening_questions: { type: Array as PropType<string[]>, default: () => [], required: true },
  text_to_speech: {
    type: Object,
    default: () => {
      return {
        enable: true,
        auto_play: true,
        voice: 'alex',
      }
    },
    required: false,
  },
})
const {
  query,
  queryTextareaRef,
  adjustQueryTextareaHeight,
  restoreQueryDraft: restoreSpaceAppDebugQueryDraft,
} = useChatQueryInput({
  getDraftKey: () =>
    `${SPACE_APP_DEBUG_QUERY_DRAFT_STORAGE_KEY_PREFIX}:${String(route.params?.app_id ?? '')}`,
  minHeight: 32,
  maxHeight: 96,
})
const image_urls = ref<string[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const setQueryTextareaRef = (element: HTMLTextAreaElement | null) => {
  queryTextareaRef.value = element
}
const setFileInputRef = (element: HTMLInputElement | null) => {
  fileInput.value = element
}
const uploadFileLoading = ref(false)
const isRecording = ref(false) // 是否正在录音
const audioBlob = ref<Blob | null>(null) // 录音后音频的blob
type RecorderLike = {
  start: () => Promise<unknown>
  stop: () => void | Promise<unknown>
  getWAVBlob: () => Blob
}
let recorder: RecorderLike | null = null // RecordRTC实例
const message_id = ref('')
const task_id = ref('')
type ScrollerLike = {
  $el?: HTMLElement
  scrollToBottom?: () => void
}
const scroller = ref<ScrollerLike | null>(null)
const scrollHeight = ref(0)
const shouldAutoScrollToBottom = ref(true)
const isStreamingResponse = ref(false)
const selectedConversationId = ref(String(route.query.conversation_id || '').trim())
const accountStore = useAccountStore()
const {
  loading: deleteDebugConversationLoading, //
  handleDeleteDebugConversation,
} = useDeleteDebugConversation()
const {
  loading: getDebugConversationMessagesWithPageLoading,
  messages,
  loadDebugConversationMessages,
} = useGetDebugConversationMessagesWithPage()
const { loading: debugChatLoading, handleDebugChat } = useDebugChat()
const { loading: stopDebugChatLoading, handleStopDebugChat } = useStopDebugChat()
const { suggested_questions, handleGenerateSuggestedQuestions } = useGenerateSuggestedQuestions()
const { loading: audioToTextLoading, text, handleAudioToText } = useAudioToText()
const { startAudioStream, stopAudioStream } = useAudioPlayer()
const { triggerFileInput, handleFileChange } = useChatImageUpload({
  imageUrls: image_urls,
  uploadFileLoading,
  fileInput,
  uploadImage,
  onError: (message) => Message.error(message),
  onSuccess: (message) => Message.success(message),
})

const normalizeConversationId = (value: unknown) => String(value || '').trim()
const normalizeMessageId = (value: unknown) => String(value || '').trim()

const emitRecentConversationsRefresh = () => {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent('recent-conversations:refresh'))
}

const syncRouteContext = async (conversation_id: string, target_message_id: string = '') => {
  const normalizedConversationId = normalizeConversationId(conversation_id)
  const normalizedMessageId = normalizeMessageId(target_message_id)
  const currentConversationId = normalizeConversationId(route.query.conversation_id)
  const currentMessageId = normalizeMessageId(route.query.message_id)

  if (
    normalizedConversationId === currentConversationId &&
    normalizedMessageId === currentMessageId
  ) {
    return
  }

  const query = { ...route.query }
  if (normalizedConversationId) {
    query.conversation_id = normalizedConversationId
  } else {
    delete query.conversation_id
  }

  if (normalizedMessageId) {
    query.message_id = normalizedMessageId
  } else {
    delete query.message_id
  }

  await router.replace({
    path: `/space/apps/${String(route.params?.app_id ?? '')}`,
    query,
  })
}

const loadConversationMessages = async (init: boolean = false) => {
  await loadDebugConversationMessages(
    String(route.params?.app_id),
    init,
    selectedConversationId.value,
  )
}

const scrollToMessage = (targetMessageId: string) => {
  const normalizedMessageId = normalizeMessageId(targetMessageId)
  if (!normalizedMessageId) return

  nextTick(() => {
    const scrollerElement = scroller.value?.$el as HTMLElement | undefined
    if (!scrollerElement) return
    const targetElement = scrollerElement.querySelector(
      `[data-index="${normalizedMessageId}"]`,
    ) as HTMLElement | null
    if (!targetElement) return
    targetElement.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'auto' })
  })
}

const focusRouteMessageIfNeeded = () => {
  const targetMessageId = normalizeMessageId(route.query.message_id)
  if (!targetMessageId) return false
  scrollToMessage(targetMessageId)
  return true
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
  handleSubmit()
}

// 2.定义保存滚动高度函数
const saveScrollHeight = () => {
  const scrollerElement = scroller.value?.$el as HTMLElement | undefined
  if (!scrollerElement) return
  scrollHeight.value = scrollerElement.scrollHeight
}

// 3.定义还原滚动高度函数
const restoreScrollPosition = () => {
  const scrollerElement = scroller.value?.$el as HTMLElement | undefined
  if (!scrollerElement) return
  scrollerElement.scrollTop = scrollerElement.scrollHeight - scrollHeight.value
}

const scrollChatToBottom = () => {
  if (!scroller.value) return
  const scrollerElement = scroller.value?.$el as HTMLElement | undefined
  if (!scrollerElement) return
  if (typeof scroller.value.scrollToBottom === 'function') {
    scroller.value.scrollToBottom()
  }
  scrollerElement.scrollTop = scrollerElement.scrollHeight
}

let scrollToBottomScheduled = false
let autoScrollTicker: number | null = null

const stopAutoScrollTicker = () => {
  if (typeof window === 'undefined') return
  if (autoScrollTicker === null) return
  window.clearInterval(autoScrollTicker)
  autoScrollTicker = null
}

const startAutoScrollTicker = () => {
  if (typeof window === 'undefined') return
  if (autoScrollTicker !== null) return

  autoScrollTicker = window.setInterval(() => {
    if (!isStreamingResponse.value || !shouldAutoScrollToBottom.value) {
      stopAutoScrollTicker()
      return
    }
    scrollChatToBottom()
  }, 80)
}

const scheduleScrollToBottom = () => {
  if (!shouldAutoScrollToBottom.value) return
  if (scrollToBottomScheduled) return
  scrollToBottomScheduled = true

  const flushScrollToBottom = () => {
    scrollToBottomScheduled = false
    if (!scroller.value || !shouldAutoScrollToBottom.value) return

    nextTick(() => {
      if (!shouldAutoScrollToBottom.value) return
      scrollChatToBottom()
      if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(() => {
          if (!shouldAutoScrollToBottom.value) return
          scrollChatToBottom()
        })
      }
    })
  }

  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(flushScrollToBottom)
    return
  }
  setTimeout(flushScrollToBottom, 16)
}

const handleScrollerWheel = (event: WheelEvent) => {
  if (!isStreamingResponse.value) return
  const hasScrollDelta = Math.abs(event.deltaX) > 0 || Math.abs(event.deltaY) > 0
  if (!hasScrollDelta) return
  shouldAutoScrollToBottom.value = false
  stopAutoScrollTicker()
}

// 4.定义滚动函数
const handleScroll = async (event: UIEvent) => {
  const { scrollTop } = event.target as HTMLElement
  if (
    scrollTop <= 0 &&
    !isStreamingResponse.value &&
    !getDebugConversationMessagesWithPageLoading.value
  ) {
    saveScrollHeight()
    await loadConversationMessages(false)
    restoreScrollPosition()
  }
}

// 5.定义输入框提交函数
const handleSubmit = async () => {
  // 5.1 检测是否录入了query，如果没有则结束
  if (query.value.trim() === '') {
    Message.warning('用户提问不能为空')
    return
  }

  // 5.2 检测上次提问是否结束，如果没结束不能发起新提问
  if (debugChatLoading.value) {
    Message.warning('上一次提问还未结束，请稍等')
    return
  }

  // 5.3 满足条件，处理正式提问的前置工作，涵盖：清空建议问题、删除消息id、任务id
  suggested_questions.value = []
  message_id.value = ''
  task_id.value = ''
  shouldAutoScrollToBottom.value = true
  stopAudioStream()

  // 5.4 往消息列表中添加基础人类消息
  messages.value.unshift({
    id: '',
    conversation_id: '',
    query: query.value,
    image_urls: image_urls.value,
    answer: '',
    total_token_count: 0,
    latency: 0,
    agent_thoughts: [],
    created_at: 0,
    suggested_questions: [],
  } as (typeof messages.value)[number])
  await nextTick(() => {
    startAutoScrollTicker()
    scrollChatToBottom()
  })

  // 5.5 初始化推理过程数据，并清空输入数据
  let streamState: StreamState = {
    position: 0,
    message_id: message_id.value,
    task_id: task_id.value,
    conversation_id: selectedConversationId.value,
  }
  const requestStartAt = Date.now()
  isStreamingResponse.value = true
  const humanQuery = query.value
  const humanImageUrls = image_urls.value
  query.value = ''
  image_urls.value = []

  // 5.6 调用hooks发起请求
  try {
    await handleDebugChat(
      props.app?.id,
      humanQuery,
      humanImageUrls,
      selectedConversationId.value,
      (event_response) => {
        const currentMessage = messages.value[0] as StreamMessage | undefined
        if (!currentMessage) return

        const streamResult = applyChatStreamEvent(currentMessage, event_response, streamState)
        streamState = streamResult.state

        if (message_id.value === '' && streamResult.state.message_id) {
          task_id.value = streamResult.state.task_id
          message_id.value = streamResult.state.message_id

          const latestConversationId = normalizeConversationId(streamResult.state.conversation_id)
          if (latestConversationId) {
            selectedConversationId.value = latestConversationId
            void syncRouteContext(latestConversationId, streamResult.state.message_id)
            emitRecentConversationsRefresh()
          }
        }

        if (streamResult.didUpdate) {
          scheduleScrollToBottom()
        }
      },
    )
  } finally {
    isStreamingResponse.value = false
    stopAutoScrollTicker()
    const requestDurationMs = Math.max(Date.now() - requestStartAt, 0)
    normalizeMessageMetrics(messages.value[0] as MessageMetrics, requestDurationMs)
  }

  // 5.7 判断是否开启建议问题生成，如果开启了则发起api请求获取数据
  if (props.suggested_after_answer.enable && message_id.value) {
    handleGenerateSuggestedQuestions(message_id.value)
    setTimeout(() => scheduleScrollToBottom(), 100)
  }

  // 5.8 检测是否自动播放，如果是则调用hooks播放音频
  if (props.text_to_speech.enable && props.text_to_speech.auto_play && message_id.value) {
    startAudioStream(message_id.value)
  }
}

// 6.定义停止调试会话函数
const handleStop = async () => {
  // 6.1 如果没有任务id或者未在加载中，则直接停止
  if (task_id.value === '' || !debugChatLoading.value) return

  // 6.2 调用api接口中断请求
  await handleStopDebugChat(props.app?.id, task_id.value)
}

const handleClearConversation = async () => {
  // 1.先调用停止响应接口
  await handleStop()

  // 2.调用api接口清空会话
  await handleDeleteDebugConversation(props.app?.id)

  // 3.重置路由会话上下文并重新加载数据
  selectedConversationId.value = ''
  message_id.value = ''
  await syncRouteContext('', '')
  await loadConversationMessages(true)
  emitRecentConversationsRefresh()
}

// 7.定义问题提交函数
const handleSubmitQuestion = async (question: string) => {
  // 1.将问题同步到query中
  query.value = question

  // 2.触发handleSubmit函数
  await handleSubmit()
}

// 10.开始录音处理器
const handleStartRecord = async () => {
  // 10.1 创建AudioRecorder
  recorder = new AudioRecorder()
  const currentRecorder = recorder

  // 10.2 开始录音并记录录音状态
  try {
    isRecording.value = true
    await currentRecorder.start()
    Message.success('开始录音')
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '录音失败'))
    isRecording.value = false
  }
}

// 11.停止录音处理器
const handleStopRecord = async () => {
  const currentRecorder = recorder
  if (currentRecorder) {
    try {
      // 11.1 等待录音停止并获取录音数据
      await currentRecorder.stop()
      audioBlob.value = currentRecorder.getWAVBlob()

      // 11.2 调用语音转文本处理器并将文本填充到query中
      await handleAudioToText(audioBlob.value)
      Message.success('语音转文本成功')
      query.value = text.value
    } catch (error: unknown) {
      Message.error(getErrorMessage(error, '录音失败'))
    } finally {
      isRecording.value = false // 标记为停止录音
    }
  }
}

// 10.页面DOM加载完毕时初始化数据
onMounted(async () => {
  restoreSpaceAppDebugQueryDraft()
  selectedConversationId.value = normalizeConversationId(route.query.conversation_id)
  await loadConversationMessages(true)
  const hasFocusedTargetMessage = focusRouteMessageIfNeeded()

  await nextTick(() => {
    // 指定了message_id时优先定位上下文，否则默认滚动到底部
    if (!hasFocusedTargetMessage) {
      scrollChatToBottom()
    }
    adjustQueryTextareaHeight()
  })
})

watch(
  () => route.query.conversation_id,
  async (newValue, oldValue) => {
    const newConversationId = normalizeConversationId(newValue)
    const oldConversationId = normalizeConversationId(oldValue)
    if (newConversationId === oldConversationId) return
    if (isStreamingResponse.value) return

    selectedConversationId.value = newConversationId
    await loadConversationMessages(true)
    if (!focusRouteMessageIfNeeded()) {
      await nextTick(() => scrollChatToBottom())
    }
  },
)

watch(
  () => route.query.message_id,
  (newValue, oldValue) => {
    const newMessageId = normalizeMessageId(newValue)
    const oldMessageId = normalizeMessageId(oldValue)
    if (!newMessageId || newMessageId === oldMessageId) return
    scrollToMessage(newMessageId)
  },
)

// 11.页面卸载后停止播放
onUnmounted(() => {
  isStreamingResponse.value = false
  stopAutoScrollTicker()
  stopAudioStream()
})
</script>

<template>
  <scroll-navigator :show-scroll-to-top-button="false">
    <div class="h-full min-h-0 flex flex-col overflow-hidden">
      <div
        v-if="getDebugConversationMessagesWithPageLoading && messages.length === 0"
        class="flex-1 min-h-0 px-6 pt-6"
      >
        <chat-conversation-skeleton :pair-count="6" />
      </div>
      <!-- 历史对话列表 -->
      <div v-else-if="messages.length > 0" class="flex-1 min-h-0 flex flex-col px-6">
        <dynamic-scroller
          ref="scroller"
          :items="messages.slice().reverse()"
          :min-item-size="1"
          @scroll="handleScroll"
          @wheel.passive="handleScrollerWheel"
          class="flex-1 min-h-0 overflow-y-auto scrollbar-w-none"
        >
          <template v-slot="{ item, active }">
            <dynamic-scroller-item :item="item" :active="active" :data-index="item.id">
              <div class="flex flex-col gap-6 py-6">
                <human-message
                  data-scroll-item
                  :query="item.query"
                  :image_urls="item.image_urls"
                  :account="accountStore.account"
                />
                <ai-message
                  :message_id="item.id"
                  :enable_text_to_speech="props.text_to_speech.enable"
                  :agent_thoughts="item.agent_thoughts"
                  :answer="item.answer"
                  :app="props.app"
                  :suggested_questions="
                    item.suggested_questions && item.suggested_questions.length > 0
                      ? item.suggested_questions
                      : item.id === message_id
                        ? suggested_questions
                        : []
                  "
                  :loading="item.id === message_id && debugChatLoading"
                  :latency="item.latency"
                  :total_token_count="item.total_token_count"
                  :agent_thought_default_visible="false"
                  :agent_thought_follow_latest="false"
                  @select-suggested-question="handleSubmitQuestion"
                />
              </div>
            </dynamic-scroller-item>
          </template>
        </dynamic-scroller>
        <!-- 停止调试会话 -->
        <div v-if="task_id && debugChatLoading" class="h-[50px] flex items-center justify-center">
          <a-button :loading="stopDebugChatLoading" class="rounded-lg px-2" @click="handleStop">
            <template #icon>
              <icon-poweroff />
            </template>
            停止响应
          </a-button>
        </div>
      </div>
      <!-- 对话列表为空时展示的对话开场白 -->
      <div
        v-else
        class="flex-1 min-h-0 flex flex-col p-6 gap-2 items-center justify-center overflow-y-auto scrollbar-w-none"
      >
        <!-- 应用图标与名称 -->
        <div class="flex flex-col items-center gap-2">
          <a-avatar :size="48" shape="square" class="rounded-lg" :image-url="props.app?.icon" />
          <div class="text-lg text-gray-700">{{ props.app?.name }}</div>
        </div>
        <!-- 对话开场白 -->
        <div
          v-if="props.opening_statement"
          class="bg-gray-100 w-full px-4 py-3 rounded-lg text-gray-700"
        >
          {{ props.opening_statement }}
        </div>
        <!-- 开场白建议问题 -->
        <div class="flex flex-col items-start gap-2 w-full">
          <div
            v-for="(opening_question, idx) in props.opening_questions.filter(
              (item) => item.trim() !== '',
            )"
            :key="idx"
            class="w-fit max-w-full px-4 py-1.5 border rounded-lg text-gray-700 cursor-pointer hover:bg-gray-50 break-words"
            @click="async () => await handleSubmitQuestion(opening_question)"
          >
            {{ opening_question }}
          </div>
        </div>
      </div>
      <!-- 对话输入框 -->
      <div class="w-full flex flex-col flex-shrink-0">
        <!-- 顶部输入框 -->
        <div class="px-6">
          <chat-composer
            v-model="query"
            size="compact"
            :textarea-ref-setter="setQueryTextareaRef"
            :file-input-ref-setter="setFileInputRef"
            :image-urls="image_urls"
            :show-image-previews="true"
            :clear-disabled="deleteDebugConversationLoading || messages.length === 0"
            :clear-loading="deleteDebugConversationLoading"
            :upload-loading="uploadFileLoading"
            :submit-loading="debugChatLoading"
            :audio-to-text-loading="audioToTextLoading"
            :is-recording="isRecording"
            clear-title="清空调试会话"
            placeholder="发送调试消息"
            @clear="handleClearConversation"
            @upload="triggerFileInput"
            @file-change="(event) => handleFileChange(event)"
            @input="() => adjustQueryTextareaHeight()"
            @keydown="(event) => handleQueryKeydown(event)"
            @remove-image="
              (index) => {
                image_urls.splice(index, 1)
              }
            "
            @start-record="handleStartRecord"
            @stop-record="handleStopRecord"
            @submit="handleSubmit"
          />
        </div>
        <!-- 底部提示信息 -->
        <div class="text-center text-gray-500 text-xs py-4">
          内容由AI生成，无法确保真实准确，仅供参考
        </div>
      </div>
      <!-- 停止会话按钮 -->
    </div>
  </scroll-navigator>
</template>
