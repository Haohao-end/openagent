<script setup lang="ts">
import AiMessage from '@/components/AiMessage.vue'
import ChatComposer from '@/components/ChatComposer.vue'
import HumanMessage from '@/components/HumanMessage.vue'
import ChatConversationSkeleton from '@/components/skeletons/ChatConversationSkeleton.vue'
import { useGenerateSuggestedQuestions } from '@/hooks/use-ai'
import { useChatImageUpload } from '@/hooks/use-chat-image-upload'
import { useAudioPlayer, useAudioToText } from '@/hooks/use-audio'
import { useChatQueryInput } from '@/hooks/use-chat-query-input'
import {
  useDeleteConversation,
  useGetConversationMessagesWithPage,
  useUpdateConversationIsPinned,
} from '@/hooks/use-conversation'
import {
  useGetAppConversations,
  useGetWebApp,
  useStopWebAppChat,
  useWebAppChat,
} from '@/hooks/use-web-app'
import { uploadImage } from '@/services/upload-file'
import { useAccountStore } from '@/stores/account'
import { Message } from '@arco-design/web-vue'
import AudioRecorder from 'js-audio-recorder'
import type { GetConversationMessagesWithPageResponse } from '@/models/conversation'
import type { GetWebAppConversationsResponse } from '@/models/web-app'
import {
  applyChatStreamEvent,
  type StreamMessage,
  type StreamState,
} from '@/views/shared/chat-stream'
import { normalizeMessageMetrics, type MessageMetrics } from '@/views/shared/chat-metrics'
import { calculateScrollDuration, smoothScroll } from '@/utils/scrollAnimation'
import { cloneDeep } from 'lodash'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import UpdateNameModal from './components/UpdateNameModal.vue'

// 1.定义页面所需数据
const route = useRoute()
const updateConversationNameModalVisible = ref(false)
const updateConversationNameId = ref('')
type ConversationSummary = GetWebAppConversationsResponse['data'][number]
type WebAppMessage = GetConversationMessagesWithPageResponse['data']['list'][number]
type RecorderLike = {
  start: () => Promise<unknown>
  stop: () => Promise<unknown> | void
  getWAVBlob: () => Blob
}
type ScrollerLike = {
  $el?: HTMLElement
  scrollToBottom?: () => void
}
const newConversation = ref<ConversationSummary | null>(null)
const selectedConversation = ref('')
const image_urls = ref<string[]>([])
const WEB_APP_QUERY_DRAFT_STORAGE_KEY_PREFIX = 'draft:web-apps:query'
const fileInput = ref<HTMLInputElement | null>(null)
const setQueryTextareaRef = (element: HTMLTextAreaElement | null) => {
  queryTextareaRef.value = element
}
const setFileInputRef = (element: HTMLInputElement | null) => {
  fileInput.value = element
}
const uploadFileLoading = ref(false)
const { triggerFileInput, handleFileChange } = useChatImageUpload({
  imageUrls: image_urls,
  uploadFileLoading,
  fileInput,
  uploadImage,
  onError: (message) => Message.error(message),
  onSuccess: (message) => Message.success(message),
})
const isRecording = ref(false) // 是否正在录音
const audioBlob = ref<Blob | null>(null) // 录音后音频的blob
let recorder: RecorderLike | null = null // RecordRTC实例
const message_id = ref('')
const task_id = ref('')
const scroller = ref<ScrollerLike | null>(null)
const scrollHeight = ref(0)
const showScrollToBottomButton = ref(false)
const humanMessageElements = ref<HTMLElement[]>([])
const currentHumanMessageIndex = ref(-1)
const HUMAN_NAV_BOTTOM_DISTANCE_THRESHOLD = 500
const accountStore = useAccountStore()
const { loading: getWebAppLoading, web_app, loadWebApp } = useGetWebApp()
const {
  loading: getWebAppConversationsLoading,
  pinned_conversations,
  unpinned_conversations,
  loadWebAppConversations,
} = useGetAppConversations()
const { handleDeleteConversation } = useDeleteConversation()
const {
  loading: getConversationMessagesWithPageLoading,
  messages,
  loadConversationMessagesWithPage,
} = useGetConversationMessagesWithPage()
const { handleUpdateConversationIsPinned } = useUpdateConversationIsPinned()
const { loading: webAppChatLoading, handleWebAppChat } = useWebAppChat()
const { loading: stopWebAppChatLoading, handleStopWebAppChat } = useStopWebAppChat()
const { suggested_questions, handleGenerateSuggestedQuestions } = useGenerateSuggestedQuestions()
const can_image_input = computed(() => {
  if (web_app.value) {
    return web_app.value?.app_config?.features?.includes('image_input')
  }
  return false
})
const can_speech_to_text = computed(() => {
  if (web_app.value) {
    return web_app.value?.app_config?.speech_to_text?.enable
  }
  return false
})
const openingQuestions = computed(() => {
  return (web_app.value?.app_config?.opening_questions || []).filter(
    (item: string) => item.trim() !== '',
  )
})
const { loading: audioToTextLoading, text, handleAudioToText } = useAudioToText()
const { startAudioStream, stopAudioStream } = useAudioPlayer()

const getWebAppQueryDraftStorageKey = () => {
  return `${WEB_APP_QUERY_DRAFT_STORAGE_KEY_PREFIX}:${String(route.params?.token ?? '')}`
}

const {
  query,
  queryTextareaRef,
  adjustQueryTextareaHeight,
  restoreQueryDraft: restoreWebAppQueryDraft,
} = useChatQueryInput({
  getDraftKey: getWebAppQueryDraftStorageKey,
  minHeight: 36,
  maxHeight: 220,
})

const isInputBreathing = computed(() => {
  return isRecording.value || audioToTextLoading.value
})

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

// 2.定义会话计算属性，动态展示当前选中会话
const conversation = computed(() => {
  // 2.1 判断是否选中新会话，如果是则直接返回新会话数据
  if (selectedConversation.value === 'new_conversation') {
    return newConversation.value
  } else if (selectedConversation.value !== '') {
    // 2.2 查询置顶会话数据，如果不为空则直接返回
    let item = pinned_conversations.value.find((item) => item.id === selectedConversation.value)
    if (item) return item

    // 2.3 置顶会话查询不到数据，则查询非置顶数据
    return unpinned_conversations.value.find((item) => item.id === selectedConversation.value)
  }
  return null
})

// 3.定义保存滚动高度函数
const saveScrollHeight = () => {
  const scrollerElement = scroller.value?.$el
  if (!scrollerElement) return
  scrollHeight.value = scrollerElement.scrollHeight
}

// 4.定义修改指定状态处理器
const changeIsPinned = async (idx: number, origin_is_pinned: boolean) => {
  // 3.1 根据idx提取数据
  const conversation = origin_is_pinned
    ? pinned_conversations.value[idx]
    : unpinned_conversations.value[idx]

  // 3.2 调用hooks发起api请求
  await handleUpdateConversationIsPinned(conversation.id, !origin_is_pinned, () => {
    // 3.3 执行成功调用回调，更新会话位置
    if (origin_is_pinned) {
      pinned_conversations.value.splice(idx, 1)
      unpinned_conversations.value.push(conversation)
    } else {
      unpinned_conversations.value.splice(idx, 1)
      pinned_conversations.value.push(conversation)
    }
  })
}

// 5.定义修改会话名字处理器
const updateName = (idx: number, origin_is_pinned: boolean) => {
  // 4.1 根据idx提取数据
  const conversation = origin_is_pinned
    ? pinned_conversations.value[idx]
    : unpinned_conversations.value[idx]

  // 4.2 更新响应数据状态
  updateConversationNameId.value = conversation.id
  updateConversationNameModalVisible.value = true
}

// 6.定义更新会话名字成功处理器
const successUpdateNameCallback = (conversation_id: string, conversation_name: string) => {
  // 5.1 先查询置顶会话对应的记录索引
  let idx = pinned_conversations.value.findIndex((item) => item.id === conversation_id)

  // 5.2 判断索引值是否为-1
  if (idx !== -1) {
    // 5.2 置顶会话
    pinned_conversations.value[idx]['name'] = conversation_name
  } else {
    idx = unpinned_conversations.value.findIndex((item) => item.id === conversation_id)
    if (idx !== -1) unpinned_conversations.value[idx]['name'] = conversation_name
  }
}

// 7.定义删除回话处理器
const deleteConversation = async (idx: number, origin_is_pinned: boolean) => {
  // 6.1 根据idx提取数据
  const conversation = origin_is_pinned
    ? pinned_conversations.value[idx]
    : unpinned_conversations.value[idx]

  // 6.2 调用hooks发起请求
  handleDeleteConversation(conversation.id, () => {
    // 6.3 执行成功调用回调，删除回话
    if (origin_is_pinned) {
      pinned_conversations.value.splice(idx, 1)
    } else {
      unpinned_conversations.value.splice(idx, 1)
    }
  })
}

// 8.定义新增会话处理器
const addConversation = () => {
  // 7.1 将选择会话切换到new_conversation
  selectedConversation.value = 'new_conversation'

  // 7.2 如果没有新会话则创建一个
  if (!newConversation.value) {
    newConversation.value = {
      id: '',
      name: 'New Conversation',
      summary: '',
      created_at: 0,
    }
  }
}

// 9.定义还原滚动高度函数
const restoreScrollPosition = () => {
  const scrollerElement = scroller.value?.$el
  if (!scrollerElement) return
  scrollerElement.scrollTop = scrollerElement.scrollHeight - scrollHeight.value
}

// 10.定义滚动函数
const updateScrollToBottomButtonVisibility = () => {
  const scrollerElement = scroller.value?.$el
  if (!scrollerElement) {
    showScrollToBottomButton.value = false
    return
  }

  const distanceToBottom =
    scrollerElement.scrollHeight - scrollerElement.scrollTop - scrollerElement.clientHeight
  showScrollToBottomButton.value = distanceToBottom > HUMAN_NAV_BOTTOM_DISTANCE_THRESHOLD
}

const updateCurrentHumanMessageIndex = () => {
  const scrollerElement = scroller.value?.$el
  if (!scrollerElement || humanMessageElements.value.length === 0) {
    currentHumanMessageIndex.value = -1
    return
  }

  const containerRect = scrollerElement.getBoundingClientRect()
  const targetTop = containerRect.top + containerRect.height * 0.35

  let bestIndex = -1
  let minDistance = Number.POSITIVE_INFINITY

  humanMessageElements.value.forEach((node, index) => {
    const rect = node.getBoundingClientRect()
    const distance = Math.abs(rect.top - targetTop)
    if (distance < minDistance) {
      minDistance = distance
      bestIndex = index
    }
  })

  currentHumanMessageIndex.value = bestIndex
}

const collectHumanMessageElements = async () => {
  await nextTick()
  const scrollerElement = scroller.value?.$el
  if (!scrollerElement) {
    humanMessageElements.value = []
    currentHumanMessageIndex.value = -1
    return
  }

  humanMessageElements.value = Array.from(
    scrollerElement.querySelectorAll('[data-human-message-anchor="true"]'),
  ) as HTMLElement[]
  updateCurrentHumanMessageIndex()
}

const scrollToBottomWithEasing = () => {
  const scrollerElement = scroller.value?.$el
  if (!scrollerElement) return

  const targetTop = Math.max(scrollerElement.scrollHeight - scrollerElement.clientHeight, 0)
  const distance = targetTop - scrollerElement.scrollTop
  if (Math.abs(distance) < 2) return

  const duration = calculateScrollDuration(distance)
  smoothScroll(scrollerElement, targetTop, duration)
}

const scrollToHumanMessageByIndex = (index: number) => {
  const scrollerElement = scroller.value?.$el
  const targetElement = humanMessageElements.value[index]
  if (!scrollerElement || !targetElement) return

  const containerRect = scrollerElement.getBoundingClientRect()
  const targetRect = targetElement.getBoundingClientRect()
  const delta = targetRect.top - containerRect.top - 12
  const targetTop = scrollerElement.scrollTop + delta
  const duration = calculateScrollDuration(targetTop - scrollerElement.scrollTop)

  smoothScroll(scrollerElement, targetTop, duration)
}

const handleScroll = async (event: UIEvent) => {
  const { scrollTop } = event.target as HTMLElement
  if (scrollTop <= 0 && !webAppChatLoading.value) {
    const currentConversation = conversation.value
    if (!currentConversation?.id) return
    saveScrollHeight()
    await loadConversationMessagesWithPage(currentConversation.id, false)
    restoreScrollPosition()
  }
}

// 11.定义输入框提交函数
const handleSubmit = async () => {
  // 11.1 检测是否录入了query，如果没有则结束
  if (query.value.trim() === '') {
    Message.warning('用户提问不能为空')
    return
  }

  // 11.2 检测上次提问是否结束，如果没结束不能发起新提问
  if (webAppChatLoading.value) {
    Message.warning('上一次提问还未结束，请稍等')
    return
  }

  // 11.3 满足条件，处理正式提问的前置工作，涵盖：清空建议问题、删除消息id、任务id
  suggested_questions.value = []
  message_id.value = ''
  task_id.value = ''
  stopAudioStream()
  const selectedConversationTmp = cloneDeep(selectedConversation.value)

  // 11.4 往消息列表中添加基础人类消息
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
  } as WebAppMessage)

  // 11.5 初始化推理过程数据，并清空输入数据
  let streamState: StreamState = {
    position: 0,
    message_id: message_id.value,
    task_id: task_id.value,
    conversation_id:
      selectedConversation.value === 'new_conversation' ? '' : selectedConversation.value,
  }
  const requestStartAt = Date.now()
  const humanQuery = query.value
  const humanImageUrls = image_urls.value
  query.value = ''
  image_urls.value = []

  // 11.6 调用hooks发起请求
  const req = {
    conversation_id:
      selectedConversation.value === 'new_conversation' ? '' : selectedConversation.value,
    query: humanQuery,
    image_urls: humanImageUrls,
  }
  let chatSucceeded = false
  try {
    await handleWebAppChat(String(route.params?.token), req, (event_response) => {
      const currentMessage = messages.value[0] as StreamMessage | undefined
      if (!currentMessage) return

      const streamResult = applyChatStreamEvent(currentMessage, event_response, streamState)
      streamState = streamResult.state

      if (message_id.value === '' && streamResult.state.message_id) {
        task_id.value = streamResult.state.task_id
        message_id.value = streamResult.state.message_id
      }

      if (streamResult.didUpdate) {
        scroller.value?.scrollToBottom?.()
      }
    })
    chatSucceeded = true
  } catch {
    const firstMessage = messages.value[0]
    let shouldRestoreInput = false
    if (
      firstMessage &&
      firstMessage.id === '' &&
      firstMessage.answer === '' &&
      firstMessage.query === humanQuery
    ) {
      messages.value.shift()
      shouldRestoreInput = true
    }
    if (shouldRestoreInput) {
      query.value = humanQuery
      image_urls.value = humanImageUrls
      await nextTick(() => adjustQueryTextareaHeight())
    }
  }

  if (!chatSucceeded) return

  normalizeMessageMetrics(
    messages.value[0] as MessageMetrics,
    Math.max(Date.now() - requestStartAt, 0),
  )

  // 11.13 消息正常判断结束的情况下，判断是否是新会话
  if (messages.value.length > 0) {
    if (selectedConversationTmp === 'new_conversation') {
      // 11.14 将newConversation填充到会话列表中
      unpinned_conversations.value.unshift({
        id: messages.value[0].conversation_id,
        name: 'New Conversation',
        summary: '',
        created_at: messages.value[0].created_at,
      })
      // 11.15 清空newConversation并修改选中
      newConversation.value = null
      if (selectedConversation.value === 'new_conversation') {
        selectedConversation.value = messages.value[0].conversation_id
      }
    }
    // 11.16 判断是否开启建议问题生成，如果开启了则发起api请求获取数据
    if (web_app.value?.app_config?.suggested_after_answer.enable && message_id.value) {
      handleGenerateSuggestedQuestions(message_id.value)
      setTimeout(() => scroller.value?.scrollToBottom?.(), 100)
    }

    // 11.17 判断是否自动播放
    if (
      web_app.value?.app_config?.text_to_speech.enable &&
      web_app.value?.app_config?.text_to_speech.auto_play &&
      message_id.value
    ) {
      startAudioStream(message_id.value)
    }
  }
}

// 12.定义切换会话处理器
const changeConversation = async (conversation_id: string) => {
  stopAudioStream()

  // 12.1 先暂停并清空会话
  await handleStop()

  // 12.2 修改激活选项
  selectedConversation.value = conversation_id
}

// 13.定义停止会话函数
const handleStop = async () => {
  // 13.1 如果没有任务id或者未在加载中，则直接停止
  if (task_id.value === '' || !webAppChatLoading.value) return

  // 13.2 调用api接口中断请求
  await handleStopWebAppChat(String(route.params?.token), task_id.value)
}

// 14.定义问题提交函数
const handleSubmitQuestion = async (question: string) => {
  // 14.1 将问题同步到query中
  query.value = question

  // 14.2 触发handleSubmit函数
  await handleSubmit()
}

// 16.开始录音处理器
const handleStartRecord = async () => {
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

// 17.停止录音处理器
const handleStopRecord = async () => {
  if (recorder) {
    try {
      // 11.1 等待录音停止并获取录音数据
      await recorder.stop()
      audioBlob.value = recorder.getWAVBlob()

      // 11.2 调用语音转文本处理器并将文本填充到query中
      await handleAudioToText(audioBlob.value)
      Message.success('语音转文本成功')
      query.value = text.value
    } catch {
      Message.error('录音失败，请检查麦克风权限后重试')
    } finally {
      isRecording.value = false // 标记为停止录音
    }
  }
}

// 18.监听选择会话变化
watch(
  () => selectedConversation.value,
  async (newValue, oldValue) => {
    if (oldValue !== undefined && newValue !== oldValue) {
      stopAudioStream()
    }

    // 15.1 判断数据的类型
    if (newValue === 'new_conversation') {
      // 15.2 点击了新会话，将消息清空
      messages.value = []
    } else if (newValue !== '') {
      await loadConversationMessagesWithPage(newValue, true)
      await nextTick(() => {
        // 15.4 确保在视图更新完成后执行滚动操作
        scroller.value?.scrollToBottom?.()
      })
    }
  },
  { immediate: true },
)

// 17.页面挂在完毕请求数据
onMounted(async () => {
  restoreWebAppQueryDraft()

  // 16.1 提取WebApp凭证标识
  const token = String(route.params?.token)

  // 16.2 异步加载数据
  try {
    await Promise.all([loadWebApp(token), loadWebAppConversations(token)])
  } catch {
    // 错误提示由 hooks 统一处理，这里仅兜底防止未处理 Promise
  }

  // 16.3 默认新增空白会话
  addConversation()
  await nextTick(() => adjustQueryTextareaHeight())
})

// 18.页面卸载后停止播放
onUnmounted(() => {
  stopAudioStream()
})
</script>

<template>
  <div class="flex min-h-screen h-full flex-col lg:flex-row">
    <!-- 左侧会话记录 -->
    <div
      class="w-full lg:w-[240px] lg:flex-shrink-0 border-b lg:border-b-0 lg:border-r border-gray-200 p-4 flex flex-col bg-white"
    >
      <!-- 顶部应用信息 -->
      <div class="flex items-center gap-3 mb-8 flex-shrink-0">
        <a-avatar :size="32" shape="square" :image-url="web_app?.icon" class="flex-shrink-0" />
        <div class="flex-1 text-base font-semibold line-clamp-1 break-all text-gray-700">
          <a-skeleton :loading="getWebAppLoading" animation>
            <a-skeleton-line :rows="1" :line-height="32" :line-spacing="4" />
          </a-skeleton>
          {{ web_app?.name }}
        </div>
      </div>
      <!-- 新增会话 -->
      <a-button type="primary" long class="rounded-lg mb-6 flex-shrink-0" @click="addConversation">
        <template #icon>
          <icon-edit />
        </template>
        新增会话
      </a-button>
      <!-- 会话列表 -->
      <div class="flex-1 overflow-scroll scrollbar-w-none">
        <!-- 置顶会话 -->
        <div class="mb-4">
          <div class="text-gray-700 font-semibold mb-2">置顶会话</div>
          <!-- 空白骨架屏 -->
          <a-skeleton :loading="getWebAppConversationsLoading" animation>
            <a-skeleton-line :rows="2" :line-height="32" :line-spacing="4" />
          </a-skeleton>
          <!-- 会话列表 -->
          <div class="flex flex-col gap-1">
            <div
              v-for="(conversation, idx) in pinned_conversations"
              :key="conversation.id"
              role="button"
              tabindex="0"
              @click="() => changeConversation(conversation.id)"
              @keydown.enter.prevent="() => changeConversation(conversation.id)"
              @keydown.space.prevent="() => changeConversation(conversation.id)"
              :class="`group flex items-center gap-1 h-8 leading-8 pl-3 pr-1 text-gray-700 rounded-lg cursor-pointer ${selectedConversation === conversation.id ? 'bg-blue-50 !text-blue-700' : ''} hover:bg-blue-50 hover:text-blue-700`"
            >
              <icon-message class="flex-shrink-0" />
              <div class="flex-1 line-clamp-1 break-all">{{ conversation.name }}</div>
              <a-dropdown position="br">
                <a-button
                  size="mini"
                  type="text"
                  class="!text-inherit !bg-transparent invisible group-hover:visible"
                >
                  <template #icon>
                    <icon-more />
                  </template>
                </a-button>
                <template #content>
                  <a-doption @click="() => changeIsPinned(idx, true)">取消置顶</a-doption>
                  <a-doption @click="() => updateName(idx, true)">重命名</a-doption>
                  <a-doption class="text-red-700" @click="() => deleteConversation(idx, true)">
                    删除
                  </a-doption>
                </template>
              </a-dropdown>
            </div>
          </div>
          <!-- 空会话列表 -->
          <a-empty v-if="!getWebAppConversationsLoading && pinned_conversations.length === 0">
            <template #image>
              <icon-empty :size="36" />
            </template>
            暂无置顶会话
          </a-empty>
        </div>
        <!-- 对话列表 -->
        <div class="mb-4">
          <div class="text-gray-700 font-semibold mb-2">对话列表</div>
          <!-- 空白骨架屏 -->
          <a-skeleton :loading="getWebAppConversationsLoading" animation>
            <a-skeleton-line :rows="2" :line-height="32" :line-spacing="4" />
          </a-skeleton>
          <!-- 会话列表 -->
          <div class="flex flex-col gap-1">
            <div
              v-if="newConversation"
              role="button"
              tabindex="0"
              :class="`group flex items-center gap-1 h-8 leading-8 pl-3 pr-1 text-gray-700 rounded-lg cursor-pointer ${selectedConversation === 'new_conversation' ? 'bg-blue-50 !text-blue-700' : ''} hover:bg-blue-50 hover:text-blue-700`"
              @click="() => changeConversation('new_conversation')"
              @keydown.enter.prevent="() => changeConversation('new_conversation')"
              @keydown.space.prevent="() => changeConversation('new_conversation')"
            >
              <icon-message class="flex-shrink-0" />
              <div class="flex-1 line-clamp-1 break-all">{{ newConversation.name }}</div>
            </div>
            <div
              v-for="(conversation, idx) in unpinned_conversations"
              :key="conversation.id"
              role="button"
              tabindex="0"
              @click="() => changeConversation(conversation.id)"
              @keydown.enter.prevent="() => changeConversation(conversation.id)"
              @keydown.space.prevent="() => changeConversation(conversation.id)"
              :class="`group flex items-center gap-1 h-8 leading-8 pl-3 pr-1 text-gray-700 rounded-lg cursor-pointer ${selectedConversation === conversation.id ? 'bg-blue-50 !text-blue-700' : ''} hover:bg-blue-50 hover:text-blue-700`"
            >
              <icon-message class="flex-shrink-0" />
              <div class="flex-1 line-clamp-1 break-all">{{ conversation.name }}</div>
              <a-dropdown position="br">
                <a-button
                  size="mini"
                  type="text"
                  class="!text-inherit !bg-transparent invisible group-hover:visible"
                >
                  <template #icon>
                    <icon-more />
                  </template>
                </a-button>
                <template #content>
                  <a-doption @click="() => changeIsPinned(idx, false)">置顶会话</a-doption>
                  <a-doption @click="() => updateName(idx, false)"> 重命名</a-doption>
                  <a-doption class="text-red-700" @click="() => deleteConversation(idx, false)">
                    删除
                  </a-doption>
                </template>
              </a-dropdown>
            </div>
          </div>
          <!-- 空会话列表 -->
          <a-empty
            v-if="
              !newConversation &&
              !getWebAppConversationsLoading &&
              unpinned_conversations.length === 0
            "
          >
            <template #image>
              <icon-empty :size="36" />
            </template>
            暂无会话列表
          </a-empty>
        </div>
      </div>
    </div>
    <!-- 右侧对话窗口 -->
    <div class="flex-1 min-h-screen bg-white flex flex-col min-h-0">
      <!-- 顶部会话名称 -->
      <div class="h-16 leading-[64px] text-base font-semibold px-6 border-b">
        {{ conversation?.name }}
      </div>
      <div
        v-if="getConversationMessagesWithPageLoading && messages.length === 0"
        class="flex-1 min-h-0 px-4 sm:px-6 pt-6 w-full max-w-[600px] mx-auto"
      >
        <chat-conversation-skeleton :pair-count="6" />
      </div>
      <!-- 底部对话消息列表 -->
      <div
        v-else-if="messages.length > 0"
        class="flex-1 min-h-0 flex flex-col px-4 sm:px-6 w-full max-w-[600px] mx-auto"
      >
        <dynamic-scroller
          ref="scroller"
          :items="messages.slice().reverse()"
          :min-item-size="1"
          @scroll="handleScroll"
          class="flex-1 min-h-0 scrollbar-w-none"
        >
          <template v-slot="{ item, active }">
            <dynamic-scroller-item :item="item" :active="active" :data-index="item.id">
              <div class="flex flex-col gap-6 py-6">
                <div data-human-message-anchor="true">
                  <human-message
                    :query="item.query"
                    :image_urls="item.image_urls"
                    :account="accountStore.account"
                  />
                </div>
                <ai-message
                  :message_id="item.id"
                  :enable_text_to_speech="web_app?.app_config?.text_to_speech?.enable"
                  :agent_thoughts="item.agent_thoughts"
                  :answer="item.answer"
                  :app="{ name: web_app.name, icon: web_app.icon }"
                  :suggested_questions="
                    item.suggested_questions && item.suggested_questions.length > 0
                      ? item.suggested_questions
                      : item.id === message_id
                        ? suggested_questions
                        : []
                  "
                  :loading="item.id === message_id && webAppChatLoading"
                  :latency="item.latency"
                  :total_token_count="item.total_token_count"
                  :agent_thought_default_visible="false"
                  :agent_thought_follow_latest="false"
                  @select-suggested-question="handleSubmitQuestion"
                  message_class="max-w-[513px]"
                />
              </div>
            </dynamic-scroller-item>
          </template>
        </dynamic-scroller>
        <!-- 停止调试会话 -->
        <div v-if="task_id && webAppChatLoading" class="h-[50px] flex items-center justify-center">
          <a-button :loading="stopWebAppChatLoading" class="rounded-lg px-2" @click="handleStop">
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
        class="flex-1 min-h-0 flex flex-col p-6 gap-2 items-center justify-center w-full max-w-[600px] mx-auto overflow-y-auto scrollbar-w-none"
      >
        <!-- 应用图标与名称 -->
        <div class="flex flex-col items-center gap-2">
          <a-avatar :size="48" shape="square" class="rounded-lg" :image-url="web_app?.icon" />
          <div class="text-lg text-gray-700">{{ web_app?.name }}</div>
        </div>
        <!-- 对话开场白 -->
        <div
          v-if="web_app?.app_config?.opening_statement"
          class="bg-gray-100 w-full px-4 py-3 rounded-lg text-gray-700"
        >
          {{ web_app?.app_config?.opening_statement }}
        </div>
        <!-- 开场白建议问题 -->
        <div class="flex items-center flex-wrap gap-2 w-full">
          <button
            v-for="(opening_question, idx) in openingQuestions"
            :key="idx"
            type="button"
            class="px-4 py-1.5 border rounded-lg text-gray-700 hover:bg-gray-50"
            @click="async () => await handleSubmitQuestion(opening_question)"
          >
            {{ opening_question }}
          </button>
        </div>
      </div>
      <!-- 对话输入框 -->
      <div class="w-full max-w-[600px] mx-auto flex flex-col flex-shrink-0">
        <!-- 顶部输入框 -->
        <div class="px-4 sm:px-6">
          <chat-composer
            v-model="query"
            :textarea-ref-setter="setQueryTextareaRef"
            :file-input-ref-setter="setFileInputRef"
            :image-urls="image_urls"
            :show-image-previews="can_image_input"
            :show-upload-button="can_image_input"
            :show-voice-button="can_speech_to_text"
            :upload-loading="uploadFileLoading"
            :submit-loading="webAppChatLoading"
            :audio-to-text-loading="audioToTextLoading"
            :is-recording="isRecording"
            :is-input-breathing="isInputBreathing"
            clear-title="新增会话"
            :placeholder="`给 &quot;${web_app?.name ?? '聊天机器人'}&quot; 发送消息`"
            @clear="addConversation"
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
    </div>
    <!-- 修改会话名字模态窗 -->
    <update-name-modal
      v-model:visible="updateConversationNameModalVisible"
      v-model:conversation_id="updateConversationNameId"
      :success_callback="successUpdateNameCallback"
    />
  </div>
</template>

<style scoped></style>
