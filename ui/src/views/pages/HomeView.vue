<script setup lang="ts">
import AiDynamicBackground from '@/components/AiDynamicBackground.vue'
import AiMessage from '@/components/AiMessage.vue'
import HumanMessage from '@/components/HumanMessage.vue'
import ChatConversationSkeleton from '@/components/skeletons/ChatConversationSkeleton.vue'
import { QueueEvent } from '@/config'
import { useGenerateSuggestedQuestions } from '@/hooks/use-ai'
import { useChatImageUpload } from '@/hooks/use-chat-image-upload'
import { useChatQueryInput } from '@/hooks/use-chat-query-input'
import {
  useAssistantAgentChat,
  useGenerateAssistantAgentIntroduction,
  useDeleteAssistantAgentConversation,
  useGetAssistantAgentMessagesWithPage,
  useStopAssistantAgentChat,
} from '@/hooks/use-assistant-agent'
import { useAudioToText, useAudioPlayer } from '@/hooks/use-audio'
import { uploadImage } from '@/services/upload-file'
import { useAccountStore } from '@/stores/account'
import { useCredentialStore } from '@/stores/credential'
import storage from '@/utils/storage'
import { Message } from '@arco-design/web-vue'
import AudioRecorder from 'js-audio-recorder'
import { computed, nextTick, onMounted, onUnmounted, onActivated, onDeactivated, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import 'github-markdown-css'
import FilingIcon from '@/assets/images/FilingIcon.png'
import LoginModal from '@/views/auth/components/LoginModal.vue'
import { useGetCurrentUser } from '@/hooks/use-account'
import { resolveHomeLoginNavigation } from '@/views/pages/home-login-flow'
import {
  applyChatStreamEvent,
  type StreamMessage,
  type StreamState,
} from '@/views/shared/chat-stream'
import {
  estimateTokenCount,
  normalizeMessageMetrics,
  toNonNegativeNumber,
  toPositiveNumber,
  type MessageMetrics,
} from '@/views/shared/chat-metrics'

// 定义组件名称以支持 keep-alive
defineOptions({
  name: 'HomeView'
})

// 1.定义页面所需数据
const homePageRef = ref<HTMLElement | null>(null)
const bottomAnchorRef = ref<HTMLElement | null>(null)
const image_urls = ref<string[]>([])
const HOME_QUERY_DRAFT_STORAGE_KEY = 'draft:home:query'
const HOME_INTRO_AUDIO_PLAYED_KEY = 'home:intro:audio:played' // localStorage key for tracking audio play status
const INPUT_BREATHE_TIMEOUT_MS = 1200
const {
  query,
  queryTextareaRef,
  adjustQueryTextareaHeight,
  restoreQueryDraft: restoreHomeQueryDraft,
} = useChatQueryInput({
  getDraftKey: () => HOME_QUERY_DRAFT_STORAGE_KEY,
  minHeight: 36,
  maxHeight: 220,
})
const fileInput = ref<HTMLInputElement | null>(null)
const uploadFileLoading = ref(false)
const { triggerFileInput: triggerChatFileInput, handleFileChange } = useChatImageUpload({
  imageUrls: image_urls,
  uploadFileLoading,
  fileInput,
  uploadImage,
  onError: (message) => Message.error(message),
  onSuccess: (message) => Message.success(message),
})
const isRecording = ref(false)  // 是否正在录音
const audioBlob = ref<Blob | null>(null)  // 录音后音频的blob
type RecorderLike = {
  start: () => Promise<unknown>
  stop: () => Promise<unknown> | void
  getWAVBlob: () => Blob
}
let recorder: RecorderLike | null = null  // RecordRTC实例
const task_id = ref('')
const message_id = ref('')
const scroller = ref<HTMLElement | null>(null)
const scrollHeight = ref(0)
const shouldAutoScrollToBottom = ref(true)
const isStreamingResponse = ref(false)
const SCROLLABLE_OVERFLOW_PATTERN = /(auto|scroll)/
const route = useRoute()
const router = useRouter()
const isHomeRoute = computed(() => route.path === '/home')
const hasLoginQueryFlag = computed(() => String(route.query.login || '') === '1')
const introductionAbortController = ref<AbortController | null>(null)
const accountStore = useAccountStore()
const credentialStore = useCredentialStore()
const { current_user, loadCurrentUser } = useGetCurrentUser()
const loginModalVisible = ref(false)
const pendingQueryAfterLogin = ref('')
const selectedConversationId = ref(String(route.query.conversation_id || '').trim())
const isAuthenticated = computed(() => {
  const now = Math.floor(Date.now() / 1000)
  return Boolean(
    credentialStore.credential.access_token &&
    credentialStore.credential.expire_at &&
    credentialStore.credential.expire_at > now,
  )
})
const userDisplayName = computed(() => {
  return (accountStore.account?.name || '').trim() || '朋友'
})
const defaultOpeningQuestions = ['你能做什么?', '帮我创建一个天气智能体', '我想做一个应用']
const HOME_INTRO_AUDIO_STREAM_ID = 'home-introduction-audio'
const opening_questions = ref<string[]>([...defaultOpeningQuestions])
const introductionLatency = ref(0)
const introductionTotalTokenCount = ref(0)
// 从 localStorage 恢复播放状态，防止刷新后重复播放
const hasIntroductionAutoPlayed = ref(storage.get(HOME_INTRO_AUDIO_PLAYED_KEY, false))
const defaultAssistantIntroduction = computed(() => {
  return [
    `### Hi，${userDisplayName.value}`,
    '',
    '你好，欢迎来到 **LLMOps** 🎉',
    '',
    '- 我可以帮你从想法出发，快速创建专属 AI 应用。',
    '- 我支持根据你的需求执行 `function call`，自动调用工具并生成垂直 Agent 的后端能力代码与配置。',
    '- 你可以把应用一键发布到 LLMOps 平台、微信等多个渠道，也可以部署到你自己的网站。',
    '',
    '**试试这些问题：**',
    '- 我想做一个应用',
    '- 帮我创建一个天气智能体',
    '- 你能做什么？',
  ].join('\n')
})
const assistantIntroduction = ref('')
const { stopAudioStream } = useAudioPlayer()
const { suggested_questions, handleGenerateSuggestedQuestions } = useGenerateSuggestedQuestions()
const {
  loading: generateAssistantAgentIntroductionLoading,
  handleGenerateAssistantAgentIntroduction,
} = useGenerateAssistantAgentIntroduction()
const { loading: assistantAgentChatLoading, handleAssistantAgentChat } = useAssistantAgentChat()
const {
  loading: stopAssistantAgentChatLoading,
  handleStopAssistantAgentChat, //
} = useStopAssistantAgentChat()
const {
  loading: getAssistantAgentMessagesWithPageLoading,
  messages,
  loadAssistantAgentMessages,
} = useGetAssistantAgentMessagesWithPage()
const {
  loading: deleteAssistantAgentConversationLoading,
  handleDeleteAssistantAgentConversation, //
} = useDeleteAssistantAgentConversation()
const {
  loading: audioToTextLoading,
  text,
  handleAudioToText,
} = useAudioToText()
const typingBreathing = ref(false)
const isInputFocused = ref(false)
let inputBreathTimer: number | null = null
const clearInputBreathTimer = () => {
  if (typeof window === 'undefined') return
  if (inputBreathTimer === null) return
  window.clearTimeout(inputBreathTimer)
  inputBreathTimer = null
}
const triggerTypingBreathing = () => {
  if (typeof window === 'undefined') return
  typingBreathing.value = true
  clearInputBreathTimer()
  inputBreathTimer = window.setTimeout(() => {
    typingBreathing.value = false
    inputBreathTimer = null
  }, INPUT_BREATHE_TIMEOUT_MS)
}
const isInputBreathing = computed(() => {
  return typingBreathing.value || isRecording.value || audioToTextLoading.value
})

const normalizeConversationId = (value: unknown) => String(value || '').trim()

const emitRecentConversationsRefresh = () => {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent('recent-conversations:refresh'))
}

const syncRouteConversationId = async (conversation_id: string) => {
  const normalizedConversationId = normalizeConversationId(conversation_id)
  const currentConversationId = normalizeConversationId(route.query.conversation_id)
  if (normalizedConversationId === currentConversationId) return

  const query = { ...route.query }
  if (normalizedConversationId) {
    query.conversation_id = normalizedConversationId
  } else {
    delete query.conversation_id
  }

  await router.replace({ path: '/home', query })
}

const normalizeAllMessageMetrics = () => {
  messages.value.forEach((message) => normalizeMessageMetrics(message as MessageMetrics))
}

const reloadAssistantMessages = async (
  init: boolean,
  conversation_id: string = selectedConversationId.value,
) => {
  await loadAssistantAgentMessages(init, conversation_id)
  normalizeAllMessageMetrics()
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

const handleQueryInput = () => {
  triggerTypingBreathing()
  adjustQueryTextareaHeight()
}

const streamingAnswer = computed(() => String(messages.value[0]?.answer || ''))
watch(streamingAnswer, () => {
  if (!isStreamingResponse.value || !shouldAutoScrollToBottom.value) return
  nextTick(() => {
    if (!isStreamingResponse.value || !shouldAutoScrollToBottom.value) return
    scrollChatToBottom()
  })
})

const resetAssistantIntroduction = () => {
  assistantIntroduction.value = defaultAssistantIntroduction.value
}

const resetAssistantIntroductionMetrics = () => {
  introductionLatency.value = 0
  introductionTotalTokenCount.value = 0
  hasIntroductionAutoPlayed.value = false
  storage.remove(HOME_INTRO_AUDIO_PLAYED_KEY) // 清除 localStorage 中的播放状态
}

const normalizeIntroductionMetrics = (requestDurationMs: number = 0, fallbackContent: string = '') => {
  const normalizedLatency = requestDurationMs > 0 ? requestDurationMs / 1000 : 0
  const normalizedContent = String(fallbackContent || assistantIntroduction.value || '').trim()

  if (introductionLatency.value <= 0) {
    introductionLatency.value = Number(normalizedLatency.toFixed(2))
  }

  if (introductionTotalTokenCount.value <= 0) {
    introductionTotalTokenCount.value = normalizedContent ? estimateTokenCount(normalizedContent) : 0
  }
}

const resetOpeningQuestions = () => {
  opening_questions.value = [...defaultOpeningQuestions]
}

const handleShowLoginModal = () => {
  loginModalVisible.value = true
}

const ensureLogin = () => {
  if (isAuthenticated.value) return true
  handleShowLoginModal()
  return false
}

const initializeHomeAfterLogin = async () => {
  await loadCurrentUser()
  if (current_user.value && Object.keys(current_user.value).length > 0) {
    accountStore.update(current_user.value)
  }

  // 无论是否指定了 conversation_id，都应该加载消息
  // 如果没有指定 conversation_id，则加载最新的会话消息
  // 如果指定了 conversation_id，则加载该会话的消息
  try {
    await reloadAssistantMessages(true, selectedConversationId.value)

    const latestConversationId = normalizeConversationId(messages.value[0]?.conversation_id)
    if (!selectedConversationId.value && latestConversationId) {
      selectedConversationId.value = latestConversationId
      await syncRouteConversationId(latestConversationId)
    }
  } catch (error) {
    console.error('Failed to load initial messages:', error)
  }

  if (isHomeRoute.value) {
    await loadAssistantIntroduction()
  }
}

const handleLoginSuccess = async () => {
  const redirectTarget = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  const navigationDecision = resolveHomeLoginNavigation({
    redirectTarget,
    hasLoginQueryFlag: hasLoginQueryFlag.value,
    hasRouteRedirectParam: Boolean(route.query.redirect),
    hasRouteTimestampParam: Boolean(route.query.t),
    selectedConversationId: selectedConversationId.value,
  })

  if (navigationDecision.type === 'redirect') {
    await router.replace(navigationDecision.target)
    return
  }

  if (navigationDecision.type === 'replace-home') {
    await router.replace({
      path: '/home',
      query: navigationDecision.query,
    })
  }

  await initializeHomeAfterLogin()
  await nextTick(() => {
    scrollChatToBottom()
    adjustQueryTextareaHeight()
  })

  const pendingQuery = pendingQueryAfterLogin.value.trim()
  pendingQueryAfterLogin.value = ''
  if (!pendingQuery) return

  query.value = pendingQuery
  await nextTick(() => adjustQueryTextareaHeight())
  await handleSubmit()
}

watch(
  () => [isAuthenticated.value, hasLoginQueryFlag.value, route.fullPath],
  ([loggedIn, hasLoginFlag]) => {
    if (!loggedIn && hasLoginFlag) {
      loginModalVisible.value = true
    }
  },
  { immediate: true },
)

watch(isAuthenticated, (loggedIn) => {
  if (loggedIn) return
  accountStore.clear()
  messages.value = []
  task_id.value = ''
  message_id.value = ''
  shouldAutoScrollToBottom.value = true
})

watch(
  () => route.query.conversation_id,
  async (newValue, oldValue) => {
    const normalizedConversationId = normalizeConversationId(newValue)
    const oldConversationId = normalizeConversationId(oldValue)
    if (normalizedConversationId === oldConversationId) return

    selectedConversationId.value = normalizedConversationId
    if (!isAuthenticated.value || !isHomeRoute.value) return

    try {
      await reloadAssistantMessages(true, selectedConversationId.value)
      await nextTick(() => scrollChatToBottom())
    } catch (error) {
      console.error('Failed to reload messages when conversation_id changed:', error)
    }
  },
)

const regenerateOpeningQuestions = async (message_id: string) => {
  if (!message_id) return

  try {
    await handleGenerateSuggestedQuestions(message_id)
    if (suggested_questions.value.length > 0) {
      opening_questions.value = suggested_questions.value.slice(0, 3)
    }
  } catch {
    resetOpeningQuestions()
  }
}

const loadAssistantIntroduction = async () => {
  if (!isHomeRoute.value || !isAuthenticated.value) return

  introductionAbortController.value?.abort()
  const controller = new AbortController()
  introductionAbortController.value = controller
  const requestStartAt = Date.now()

  resetAssistantIntroduction()
  resetAssistantIntroductionMetrics()
  resetOpeningQuestions()
  let introductionBuffer = ''
  let finalizedIntroduction = ''
  let suggestedQuestionsMessageId = ''
  let renderScheduled = false

  const flushStreamingIntroduction = () => {
    renderScheduled = false
    if (!controller.signal.aborted && introductionBuffer.trim()) {
      assistantIntroduction.value = introductionBuffer
    }
  }

  const scheduleStreamingIntroductionRender = () => {
    if (renderScheduled) return
    renderScheduled = true
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(flushStreamingIntroduction)
      return
    }
    setTimeout(flushStreamingIntroduction, 16)
  }

  try {
    await handleGenerateAssistantAgentIntroduction(
      (event_response) => {
        if (controller.signal.aborted) return
        const event = event_response?.event
        const data = event_response?.data || {}

        if (event === 'intro_chunk') {
          introductionBuffer += data?.content || ''
          scheduleStreamingIntroductionRender()
        } else if (event === 'intro_done') {
          if (renderScheduled) {
            flushStreamingIntroduction()
          }

          const is_first_time = Boolean(data?.is_first_time)
          suggestedQuestionsMessageId =
            data?.suggested_questions_message_id || data?.message_id || ''
          if (!is_first_time) {
            const introduction = (data?.content || introductionBuffer || '').trim()
            if (introduction) {
              assistantIntroduction.value = introduction
              finalizedIntroduction = introduction
            }
          } else {
            finalizedIntroduction = (assistantIntroduction.value || '').trim()
          }

          const eventLatency = toPositiveNumber(data?.latency)
          const eventTokenCount = Math.floor(toNonNegativeNumber(data?.total_token_count))
          if (eventLatency > 0) {
            introductionLatency.value = Number(eventLatency.toFixed(2))
          }
          if (eventTokenCount > 0) {
            introductionTotalTokenCount.value = eventTokenCount
          }
        } else if (event === QueueEvent.error || event === 'error') {
          resetAssistantIntroduction()
          resetAssistantIntroductionMetrics()
        }
      },
      controller.signal,
    )

    if (controller.signal.aborted) return
    const requestDurationMs = Math.max(Date.now() - requestStartAt, 0)
    normalizeIntroductionMetrics(requestDurationMs, finalizedIntroduction || introductionBuffer)
    await regenerateOpeningQuestions(suggestedQuestionsMessageId)

    // 默认不自动播放音频，用户可手动点击播放按钮
  } catch (error: unknown) {
    if (!(error instanceof Error && error.name === 'AbortError')) {
      resetAssistantIntroduction()
      normalizeIntroductionMetrics(Math.max(Date.now() - requestStartAt, 0))
      resetOpeningQuestions()
    }
  } finally {
    if (introductionAbortController.value === controller) {
      introductionAbortController.value = null
    }
  }
}

// 2.定义保存滚动高度函数
const saveScrollHeight = () => {
  const scrollerElement = scroller.value
  if (!scrollerElement) return
  scrollHeight.value = scrollerElement.scrollHeight
}

// 3.定义还原滚动高度函数
const restoreScrollPosition = () => {
  const scrollerElement = scroller.value
  if (!scrollerElement) return
  scrollerElement.scrollTop = scrollerElement.scrollHeight - scrollHeight.value
}

const scrollChatToBottom = () => {
  const scrollerElement = scroller.value
  if (!scrollerElement) return

  if (bottomAnchorRef.value) {
    bottomAnchorRef.value.scrollIntoView({
      block: 'end',
      inline: 'nearest',
      behavior: 'auto',
    })
  }

  scrollerElement.scrollTop = scrollerElement.scrollHeight

  // 兜底：寻找真实的可滚动父容器，确保命中页面实际滚动区域
  let cursorElement: HTMLElement | null = scrollerElement
  while (cursorElement) {
    const parentElementNode: HTMLElement | null =
      cursorElement.parentElement as HTMLElement | null
    if (!parentElementNode) break

    const style = window.getComputedStyle(parentElementNode)
    const isScrollableByStyle =
      SCROLLABLE_OVERFLOW_PATTERN.test(style.overflowY) ||
      SCROLLABLE_OVERFLOW_PATTERN.test(style.overflow)
    const hasScrollableSpace =
      parentElementNode.scrollHeight > parentElementNode.clientHeight

    if (isScrollableByStyle && hasScrollableSpace) {
      parentElementNode.scrollTop = parentElementNode.scrollHeight
    }
    cursorElement = parentElementNode
  }

  // 兜底：在页面级滚动容器中也尽量保持在底部
  if (typeof document !== 'undefined') {
    const pageScroller = document.scrollingElement as HTMLElement | null
    if (pageScroller) {
      pageScroller.scrollTop = pageScroller.scrollHeight
    }
  }
  if (homePageRef.value) {
    homePageRef.value.scrollTop = homePageRef.value.scrollHeight
  }
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    window.scrollTo({
      top: document.documentElement.scrollHeight,
      behavior: 'auto',
    })
  }
}

let scrollToBottomScheduled = false
let autoScrollTicker: number | null = null
let autoScrollObserver: MutationObserver | null = null

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

const stopAutoScrollObserver = () => {
  if (autoScrollObserver) {
    autoScrollObserver.disconnect()
    autoScrollObserver = null
  }
}

const startAutoScrollObserver = () => {
  if (typeof window === 'undefined') return
  if (autoScrollObserver) return
  const scrollerElement = scroller.value
  if (!scrollerElement) return

  autoScrollObserver = new MutationObserver(() => {
    if (!isStreamingResponse.value || !shouldAutoScrollToBottom.value) return
    scrollChatToBottom()
  })

  autoScrollObserver.observe(scrollerElement, {
    childList: true,
    subtree: true,
    characterData: true,
  })
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

      // 二次贴底，覆盖内容高度在下一帧继续增长的场景
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
  stopAutoScrollObserver()
  stopAutoScrollTicker()
}

// 4.定义滚动函数
const handleScroll = (event: Event) => {
  const target = event.target as HTMLElement | null
  if (!target) return
  const { scrollTop } = target

  if (
    scrollTop <= 0 &&
    !isStreamingResponse.value &&
    !getAssistantAgentMessagesWithPageLoading.value
  ) {
    saveScrollHeight()
    void (async () => {
      await reloadAssistantMessages(false)
      restoreScrollPosition()
    })()
  }
}

// 5.定义输入框提交函数
const handleSubmit = async () => {
  // 5.1 检测是否录入了query，如果没有则结束
  if (query.value.trim() === '') {
    Message.warning('用户提问不能为空')
    return
  }

  if (!isAuthenticated.value) {
    pendingQueryAfterLogin.value = query.value
    handleShowLoginModal()
    return
  }

  // 5.2 检测上次提问是否结束，如果没结束不能发起新提问
  if (assistantAgentChatLoading.value) {
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
    suggested_questions: [],
    created_at: 0,
  })
  await nextTick(() => {
    startAutoScrollTicker()
    startAutoScrollObserver()
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
    await handleAssistantAgentChat(
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
            void syncRouteConversationId(latestConversationId)
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
    stopAutoScrollObserver()
    stopAutoScrollTicker()
    const requestDurationMs = Math.max(Date.now() - requestStartAt, 0)
    normalizeMessageMetrics(messages.value[0] as MessageMetrics, requestDurationMs)
  }

  // 聊天响应完成后，重新加载消息以确保数据同步
  // 注意：这个操作应该在 finally 块外执行，避免错误被吞掉
  if (message_id.value && selectedConversationId.value) {
    try {
      await reloadAssistantMessages(true, selectedConversationId.value)
    } catch (error) {
      // 重新加载消息失败时，不影响用户体验
      console.error('Failed to reload messages:', error)
    }
  }

  // 5.7 发起API请求获取建议问题列表
  if (message_id.value) {
    await handleGenerateSuggestedQuestions(message_id.value)
    setTimeout(() => {
      scheduleScrollToBottom()
    }, 100)
  }

  // 默认不自动播放音频，用户可手动点击播放按钮
}

// 6.定义停止调试会话函数
const handleStop = async () => {
  // 6.1 如果没有任务id或者未在加载中，则直接停止
  if (task_id.value === '' || !assistantAgentChatLoading.value) return

  // 6.2 调用api接口中断请求
  await handleStopAssistantAgentChat(task_id.value)
}

const handleClearConversation = async () => {
  if (!ensureLogin()) return

  try {
    // 1.先调用停止响应接口
    await handleStop()

    // 2.调用api接口清空会话
    await handleDeleteAssistantAgentConversation()

    // 3.重新获取数据
    selectedConversationId.value = ''
    await syncRouteConversationId('')
    await reloadAssistantMessages(true, '')
    await loadAssistantIntroduction()
    emitRecentConversationsRefresh()
  } catch (error) {
    console.error('Failed to clear conversation:', error)
    Message.error('清空会话失败，请重试')
  }
}

// 7.定义问题提交函数
const handleSubmitQuestion = async (question: string) => {
  if (!isAuthenticated.value) {
    query.value = question
    pendingQueryAfterLogin.value = question
    handleShowLoginModal()
    return
  }

  // 1.将问题同步到query中
  query.value = question

  // 2.触发handleSubmit函数
  await handleSubmit()
}

// 8.定义文件上传触发器
const handleTriggerFileInput = () => {
  if (!ensureLogin()) return
  triggerChatFileInput()
}

// 10.开始录音处理器
const handleStartRecord = async () => {
  if (!ensureLogin()) return

  // 10.1 创建AudioRecorder
  recorder = new AudioRecorder()

  // 10.2 开始录音并记录录音状态
  try {
    isRecording.value = true
    await recorder.start()
    Message.success('开始录音')
  } catch {
    Message.error('录音失败，请检查麦克风权限后重试')
    isRecording.value = false
  }
}

// 11.停止录音处理器
const handleStopRecord = async () => {
  if (recorder) {
    try {
      // 11.1 等待录音停止并获取录音数据
      await recorder.stop()
      audioBlob.value = recorder.getWAVBlob()

      // 11.2 调用语音转文本处理器并将文本填充到query中
      await handleAudioToText(audioBlob.value)
      query.value = text.value
    } catch {
      Message.error('录音失败，请检查麦克风权限后重试')
    } finally {
      isRecording.value = false // 标记为停止录音
    }
  }
}


// 12.页面DOM加载完毕时初始化数据（仅首次挂载）
onMounted(async () => {
  restoreHomeQueryDraft()
  resetAssistantIntroduction()
  resetOpeningQuestions()

  if (isAuthenticated.value) {
    await initializeHomeAfterLogin()
  } else {
    accountStore.clear()
    messages.value = []
  }
  await nextTick(() => {
    // 确保在视图更新完成后执行滚动操作
    scrollChatToBottom()
    adjustQueryTextareaHeight()
  })
})

// 13.组件被 keep-alive 激活时的处理（从其他页面返回时）
onActivated(() => {
  if (!isAuthenticated.value) {
    accountStore.clear()
    messages.value = []
    task_id.value = ''
    message_id.value = ''
    resetAssistantIntroduction()
    resetOpeningQuestions()
  }

  // 组件被激活时不重新调用意图识别接口
  // 只需要确保滚动位置正确即可
  nextTick(() => {
    scrollChatToBottom()
    adjustQueryTextareaHeight()
  })
})

// 14.组件被 keep-alive 停用时的处理（切换到其他页面时）
onDeactivated(() => {
  // 停止音频播放，避免切换页面后音频继续播放
  stopAudioStream()
})

onUnmounted(() => {
  clearInputBreathTimer()
  typingBreathing.value = false
  introductionAbortController.value?.abort()
  introductionAbortController.value = null
  stopAutoScrollObserver()
  stopAutoScrollTicker()
  stopAudioStream()
})
</script>

<template>
  <div
    ref="homePageRef"
    class="relative w-full h-full min-h-screen overflow-y-auto"
    style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 25%, #f3e8ff 50%, #fce7f3 75%, #f0f9ff 100%);"
  >
    <!-- AI 动态背景层 -->
    <div class="absolute inset-0 z-0 pointer-events-none">
      <AiDynamicBackground
        className=""
        intensity="high"
        :showParticles="true"
        :showGrid="true"
      />
    </div>

    <!-- 内容层 -->
    <div class="relative z-10 w-full max-w-[600px] h-full min-h-screen mx-auto px-3 sm:px-4 md:px-0 flex flex-col">
      <div
        v-if="getAssistantAgentMessagesWithPageLoading && messages.length === 0"
        class="flex-1 min-h-0 px-4 sm:px-6 pt-6"
      >
        <chat-conversation-skeleton :pair-count="6" />
      </div>
      <!-- 历史对话列表 -->
      <div v-else-if="messages.length > 0" class="flex-1 min-h-0 flex flex-col px-4 sm:px-6">
        <div
          ref="scroller"
          class="flex-1 min-h-0 overflow-y-auto scrollbar-w-none"
          @scroll="handleScroll"
          @wheel.passive="handleScrollerWheel"
        >
          <div
            v-for="item in messages.slice().reverse()"
            :key="item.id || item.created_at"
            class="flex flex-col gap-6 py-6"
          >
            <human-message :query="item.query" :image_urls="item.image_urls" :account="accountStore.account" />
            <ai-message :message_id="item.id" :enable_text_to_speech="true" :agent_thoughts="item.agent_thoughts"
              :answer="item.answer" :app="{ name: '辅助Agent' }"
              :suggested_questions="item.suggested_questions && item.suggested_questions.length > 0 ? item.suggested_questions : (item.id === message_id ? suggested_questions : [])"
              :loading="item.id === message_id && assistantAgentChatLoading" :latency="item.latency"
              :total_token_count="item.total_token_count" message_class="glass-message-bubble bg-white/40 backdrop-blur-md border border-white/60 text-gray-700 px-4 py-3 rounded-2xl break-all w-fit max-w-full shadow-lg shadow-blue-500/5"
              agent_thought_variant="inline"
              :agent_thought_default_visible="false"
              @select-suggested-question="handleSubmitQuestion" />
          </div>
          <div ref="bottomAnchorRef" class="w-full h-px"></div>
        </div>
        <!-- 停止调试会话 -->
        <div v-if="task_id && assistantAgentChatLoading" class="h-[50px] flex items-center justify-center">
          <a-button :loading="stopAssistantAgentChatLoading" class="rounded-lg px-2" @click="handleStop">
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
        class="flex-1 min-h-0 flex flex-col p-6 pt-8 gap-2 items-center justify-start overflow-y-auto scrollbar-w-none"
      >
        <div class="mb-9">
          <div class="text-[40px] font-bold text-gray-700 mt-[52px] mb-4">
            Hi，{{ userDisplayName }}
          </div>
          <div class="text-[30px] font-bold text-gray-700 mb-2">
            你的专属
            <span class="text-blue-700">AI 原生应用</span>
            开发平台
          </div>
          <div class="text-base text-gray-700">
            说出你的创意，我可以快速帮你创建专属应用，一键轻松分享给朋友，也可以一键发布到
            LLMOps 平台、微信等多个渠道。
          </div>
        </div>
        <!-- 开场AI对话消息 -->
        <div class="w-full">
          <ai-message
            message_id=""
            :audio_stream_id="HOME_INTRO_AUDIO_STREAM_ID"
            :enable_text_to_speech="true"
            :agent_thoughts="[]"
            :answer="assistantIntroduction"
            :app="{ name: '辅助Agent' }"
            :loading="generateAssistantAgentIntroductionLoading && assistantIntroduction.trim() === ''"
            :latency="introductionLatency"
            :total_token_count="introductionTotalTokenCount"
            :show_agent_thought="false"
            :always_show_actions="true"
            :suggested_questions="opening_questions"
            message_class="glass-message-bubble bg-white/50 backdrop-blur-xl border border-white/80 text-gray-700 px-4 py-3 rounded-2xl break-all w-fit max-w-full shadow-xl shadow-cyan-200/30"
            @select-suggested-question="handleSubmitQuestion"
          />
        </div>
      </div>
      <!-- 对话输入框 -->
      <div class="w-full flex flex-col flex-shrink-0 px-2 sm:px-4 pb-2 pt-2 gap-3">
        <!-- 输入框容器 -->
        <div class="grid w-full grid-cols-[auto_minmax(0,1fr)] items-center gap-3">
          <!-- 清空会话按钮 -->
          <button
            @click="handleClearConversation"
            :disabled="deleteAssistantAgentConversationLoading || messages.length === 0"
            :class="[
              'flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 border',
              messages.length > 0
                ? 'bg-white/40 backdrop-blur-md border-white/60 text-gray-600 hover:bg-white/60 hover:text-red-600 hover:border-red-300/60 hover:shadow-md hover:shadow-red-200/20'
                : 'bg-white/20 border-white/40 text-gray-400 cursor-not-allowed opacity-70',
            ]"
            :title="messages.length > 0 ? '清空会话' : '暂无可清空的会话'"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>

          <!-- 输入框主体 -->
          <div
            :class="[
              'min-w-0 native-glass-input-shell rounded-2xl px-3 sm:px-4 py-2.5 grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 transition-all duration-300',
              { 'native-glass-input-shell--breathing': isInputBreathing },
              { 'native-glass-input-shell--focused': isInputFocused },
            ]"
            @click.self="queryTextareaRef?.focus()"
          >
            <!-- 上传按钮 -->
            <button
              @click="handleTriggerFileInput"
              class="input-action-btn text-gray-600 hover:bg-white/20 hover:text-gray-800"
              title="上传图片"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
              </svg>
            </button>

            <!-- 输入框 -->
            <input
              type="file"
              ref="fileInput"
              accept="image/*"
              @change="handleFileChange"
              class="hidden"
            />

            <textarea
              ref="queryTextareaRef"
              v-model="query"
              rows="1"
              class="native-glass-textarea min-w-0 w-full bg-transparent outline-none text-gray-800 placeholder-gray-500 resize-none"
              placeholder="发送消息或创建AI应用..."
              @input="handleQueryInput"
              @keydown="handleQueryKeydown"
              @focus="isInputFocused = true"
              @blur="isInputFocused = false"
            />

            <!-- 操作按钮 -->
            <div class="flex items-center gap-1.5 flex-shrink-0 self-center">
              <!-- 语音按钮 -->
              <button
                v-if="!audioToTextLoading && !isRecording"
                @click="handleStartRecord"
                class="input-action-btn text-gray-600 hover:bg-white/20 hover:text-gray-800"
                title="开始录音"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <rect x="9" y="3" width="6" height="11" rx="3" stroke-width="1.9" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.9" d="M6 10.5v1a6 6 0 0 0 12 0v-1M12 17.5V21M8.5 21h7" />
                </svg>
              </button>

              <button
                v-else-if="isRecording"
                @click="handleStopRecord"
                class="input-action-btn text-red-500 hover:bg-red-50/60 hover:text-red-600 animate-pulse"
                title="停止录音"
              >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 4h12v12H6z" />
                </svg>
              </button>

              <button
                v-else
                disabled
                class="input-action-btn cursor-wait text-cyan-500/80"
                title="正在转写"
              >
                <svg class="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle class="opacity-25" cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" />
                  <path class="opacity-90" d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                </svg>
              </button>

              <!-- 发送按钮 -->
              <button
                @click="handleSubmit"
                :disabled="assistantAgentChatLoading"
                class="input-action-btn text-cyan-600 hover:bg-cyan-500/20 hover:text-cyan-700 disabled:opacity-50"
                title="发送消息"
              >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M16.6915026,12.4744748 L3.50612381,13.2599618 C3.19218622,13.2599618 3.03521743,13.4170592 3.03521743,13.5741566 L1.15159189,20.0151496 C0.8376543,20.8006365 0.99,21.89 1.77946707,22.52 C2.41,22.99 3.50612381,23.1 4.13399899,22.8429026 L21.714504,14.0454487 C22.6563168,13.5741566 23.1272231,12.6315722 22.9702544,11.6889879 L4.13399899,1.16346272 C3.34915502,0.9 2.40734225,1.00636533 1.77946707,1.4776575 C0.994623095,2.10604706 0.837654326,3.0486314 1.15159189,3.99701575 L3.03521743,10.4380088 C3.03521743,10.5951061 3.19218622,10.7522035 3.50612381,10.7522035 L16.6915026,11.5376905 C16.6915026,11.5376905 17.1624089,11.5376905 17.1624089,12.0089827 C17.1624089,12.4744748 16.6915026,12.4744748 16.6915026,12.4744748 Z" />
                </svg>
              </button>
            </div>
          </div>

        </div>

        <!-- 底部提示 -->
        <div class="flex items-center justify-center gap-2 text-xs text-[#d0d7e0] pb-2 px-2 min-w-0">
          <span class="whitespace-nowrap">我的内容由AI生成，无法确保真实准确，仅供参考</span>
          <span class="whitespace-nowrap">© 2026 OpenAgent</span>
          <a
            href="https://beian.miit.gov.cn"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center leading-none hover:opacity-80 transition-opacity whitespace-nowrap"
          >
            桂ICP备2026003219号
          </a>
          <a
            href="http://www.beian.gov.cn/portal/registerSystemInfo?recordcode=45010202000868"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center leading-none hover:opacity-80 transition-opacity whitespace-nowrap"
          >
            <img :src="FilingIcon" alt="备案图标" class="w-2.5 h-2.5 mr-0.5 block shrink-0" />
            <span>桂公网安备45010202000868号</span>
          </a>
          <a
            href="https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center justify-center leading-none hover:opacity-80 transition-opacity"
            title="GitHub"
          >
            <svg class="w-3 h-3 block" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
          </a>
        </div>
      </div>
    </div>
    <login-modal v-model:visible="loginModalVisible" @success="handleLoginSuccess" />
  </div>
</template>

<style scoped>
.chat-input-shell {
  max-height: 336px;
  transition: all 0.3s ease;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.4) 0%, rgba(240, 249, 255, 0.3) 100%);
  border: 1px solid rgba(255, 255, 255, 0.5);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.4), inset 0 -1px 0 rgba(0, 0, 0, 0.02);
}

.chat-input-shell--breathing {
  animation: input-breathe-wave 1.4s ease-in-out infinite;
}

.chat-input-shell--focused:focus-within {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.6) 0%, rgba(240, 249, 255, 0.5) 100%);
  border-color: rgba(125, 211, 252, 0.8);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5), inset 0 -1px 0 rgba(0, 0, 0, 0.02), 0 0 0 3px rgba(125, 211, 252, 0.2);
}

.chat-query-textarea {
  width: 100%;
  min-height: 36px;
  max-height: 220px;
  padding: 7px 0;
  margin: 0;
  border: 0;
  resize: none;
  outline: none;
  line-height: 22px;
  background: transparent;
  color: #374151;
  scrollbar-width: none;
  -ms-overflow-style: none;
  overscroll-behavior: contain;
}

.chat-query-textarea::-webkit-scrollbar {
  width: 0;
  height: 0;
}

.chat-query-textarea::placeholder {
  color: #9ca3af;
}

.chat-query-textarea:focus {
  outline: none;
  box-shadow: none;
}

.chat-input-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  align-self: center;
  padding-bottom: 1px;
}

.chat-action-btn {
  width: 36px;
  height: 36px;
}

.chat-action-btn--breathing {
  animation: mic-breathe 1.3s ease-in-out infinite;
}

@keyframes input-breathe-wave {
  0% {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.4) 0%, rgba(240, 249, 255, 0.3) 100%);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.4), inset 0 -1px 0 rgba(0, 0, 0, 0.02), 0 0 0 0 rgba(125, 211, 252, 0.2);
  }
  50% {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.55) 0%, rgba(240, 249, 255, 0.45) 100%);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5), inset 0 -1px 0 rgba(0, 0, 0, 0.02), 0 0 0 6px rgba(125, 211, 252, 0.15);
  }
  100% {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.4) 0%, rgba(240, 249, 255, 0.3) 100%);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.4), inset 0 -1px 0 rgba(0, 0, 0, 0.02), 0 0 0 0 rgba(125, 211, 252, 0.2);
  }
}

@keyframes mic-breathe {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.88;
  }
  50% {
    transform: scale(1.08);
    opacity: 1;
  }
}

/* 玻璃样式 */
.glass-message-bubble {
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

/* 原生玻璃卡片 */
.native-glass-card {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.7) 0%, rgba(240, 249, 255, 0.6) 100%);
  -webkit-backdrop-filter: blur(16px);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6), 0 8px 32px rgba(0, 0, 0, 0.08);
}

/* 原生玻璃按钮 */
.native-glass-button {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.5) 0%, rgba(240, 249, 255, 0.4) 100%);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.4);
  transition: all 0.3s ease;
}

.native-glass-button:hover {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.7) 0%, rgba(240, 249, 255, 0.6) 100%);
  border-color: rgba(125, 211, 252, 0.6);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5), 0 4px 12px rgba(125, 211, 252, 0.15);
}

/* 原生玻璃输入框 */
.native-glass-input-shell {
  min-width: 0;
  min-height: 56px;
  background:
    linear-gradient(0deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.96)) padding-box,
    linear-gradient(
      135deg,
      rgba(56, 189, 248, 0.36) 0%,
      rgba(167, 139, 250, 0.3) 52%,
      rgba(244, 114, 182, 0.36) 100%
    ) border-box;
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  border: 2px solid transparent;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.88),
    inset 0 -1px 0 rgba(15, 23, 42, 0.04),
    0 10px 28px rgba(14, 165, 233, 0.08);
  transition: all 0.3s ease;
}

.native-glass-input-shell:focus-within,
.native-glass-input-shell--focused {
  background:
    linear-gradient(0deg, rgba(255, 255, 255, 1), rgba(255, 255, 255, 1)) padding-box,
    linear-gradient(135deg, #38bdf8 0%, #a78bfa 52%, #f472b6 100%) border-box;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.96),
    inset 0 -1px 0 rgba(15, 23, 42, 0.04),
    0 0 0 4px rgba(125, 211, 252, 0.12),
    0 14px 40px rgba(14, 165, 233, 0.1);
}

.native-glass-input-shell--breathing {
  animation: native-input-breathe 1.4s ease-in-out infinite;
}

.input-action-btn {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 12px;
  transition:
    color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.input-action-btn:disabled {
  cursor: not-allowed;
}

.native-glass-textarea {
  width: 100%;
  min-width: 0;
  min-height: 36px;
  margin: 0;
  padding: 7px 0;
  border: 0;
  font-size: 14px;
  line-height: 1.5;
  color: #1f2937;
  caret-color: #0ea5e9;
  max-height: 120px;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.native-glass-textarea::-webkit-scrollbar {
  width: 4px;
}

.native-glass-textarea::-webkit-scrollbar-track {
  background: transparent;
}

.native-glass-textarea::-webkit-scrollbar-thumb {
  background: rgba(125, 211, 252, 0.3);
  border-radius: 2px;
}

.native-glass-textarea::-webkit-scrollbar-thumb:hover {
  background: rgba(125, 211, 252, 0.5);
}

@keyframes native-input-breathe {
  0% {
    background:
      linear-gradient(0deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.96)) padding-box,
      linear-gradient(
        135deg,
        rgba(56, 189, 248, 0.36) 0%,
        rgba(167, 139, 250, 0.3) 52%,
        rgba(244, 114, 182, 0.36) 100%
      ) border-box;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.88),
      inset 0 -1px 0 rgba(15, 23, 42, 0.04),
      0 0 0 0 rgba(125, 211, 252, 0.08);
  }
  50% {
    background:
      linear-gradient(0deg, rgba(255, 255, 255, 0.98), rgba(255, 255, 255, 0.98)) padding-box,
      linear-gradient(
        135deg,
        rgba(56, 189, 248, 0.62) 0%,
        rgba(167, 139, 250, 0.52) 52%,
        rgba(244, 114, 182, 0.62) 100%
      ) border-box;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.94),
      inset 0 -1px 0 rgba(15, 23, 42, 0.04),
      0 0 0 5px rgba(125, 211, 252, 0.1),
      0 12px 32px rgba(167, 139, 250, 0.1);
  }
  100% {
    background:
      linear-gradient(0deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.96)) padding-box,
      linear-gradient(
        135deg,
        rgba(56, 189, 248, 0.36) 0%,
        rgba(167, 139, 250, 0.3) 52%,
        rgba(244, 114, 182, 0.36) 100%
      ) border-box;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.88),
      inset 0 -1px 0 rgba(15, 23, 42, 0.04),
      0 0 0 0 rgba(125, 211, 252, 0.08);
  }
}
</style>
