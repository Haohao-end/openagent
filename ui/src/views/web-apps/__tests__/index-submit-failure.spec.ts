import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import WebAppsIndexView from '@/views/web-apps/IndexView.vue'

const mocks = vi.hoisted(() => ({
  state: {
    query: null as null | { value: string },
    messages: null as null | { value: Array<Record<string, any>> },
    webApp: null as null | { value: Record<string, any> },
    pinnedConversations: null as null | { value: Array<Record<string, any>> },
    unpinnedConversations: null as null | { value: Array<Record<string, any>> },
  },
  loadWebApp: vi.fn().mockResolvedValue(undefined),
  loadWebAppConversations: vi.fn().mockResolvedValue(undefined),
  handleWebAppChat: vi.fn().mockRejectedValue(new Error('网络异常')),
  handleStopWebAppChat: vi.fn().mockResolvedValue(undefined),
  loadConversationMessagesWithPage: vi.fn().mockResolvedValue(undefined),
  handleDeleteConversation: vi.fn(),
  handleUpdateConversationIsPinned: vi.fn().mockResolvedValue(undefined),
  handleGenerateSuggestedQuestions: vi.fn().mockResolvedValue(undefined),
  triggerFileInput: vi.fn(),
  handleFileChange: vi.fn(),
  adjustQueryTextareaHeight: vi.fn(),
  restoreQueryDraft: vi.fn(),
  stopAudioStream: vi.fn(),
  startAudioStream: vi.fn(),
  handleAudioToText: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({
      params: { token: 'token-1' },
      query: {},
    }),
  }
})

vi.mock('@/stores/account', () => ({
  useAccountStore: () => ({
    account: {
      name: 'Tester',
      avatar: '',
    },
  }),
}))

vi.mock('@/hooks/use-chat-query-input', async () => {
  const { ref } = await import('vue')
  if (!mocks.state.query) {
    mocks.state.query = ref('')
  }
  return {
    useChatQueryInput: () => ({
      query: mocks.state.query,
      queryTextareaRef: ref<HTMLTextAreaElement | null>(null),
      adjustQueryTextareaHeight: mocks.adjustQueryTextareaHeight,
      restoreQueryDraft: mocks.restoreQueryDraft,
    }),
  }
})

vi.mock('@/hooks/use-conversation', async () => {
  const { ref } = await import('vue')
  if (!mocks.state.messages) {
    mocks.state.messages = ref<Array<Record<string, any>>>([])
  }
  return {
    useDeleteConversation: () => ({
      handleDeleteConversation: mocks.handleDeleteConversation,
    }),
    useGetConversationMessagesWithPage: () => ({
      loading: ref(false),
      messages: mocks.state.messages,
      loadConversationMessagesWithPage: mocks.loadConversationMessagesWithPage,
    }),
    useUpdateConversationIsPinned: () => ({
      handleUpdateConversationIsPinned: mocks.handleUpdateConversationIsPinned,
    }),
  }
})

vi.mock('@/hooks/use-web-app', async () => {
  const { ref } = await import('vue')
  if (!mocks.state.webApp) {
    mocks.state.webApp = ref({
      name: '测试机器人',
      icon: '',
      app_config: {
        features: [],
        speech_to_text: { enable: false },
        suggested_after_answer: { enable: false },
        text_to_speech: { enable: false, auto_play: false },
        opening_questions: [],
      },
    })
  }
  if (!mocks.state.pinnedConversations) {
    mocks.state.pinnedConversations = ref([])
  }
  if (!mocks.state.unpinnedConversations) {
    mocks.state.unpinnedConversations = ref([])
  }
  return {
    useGetWebApp: () => ({
      loading: ref(false),
      web_app: mocks.state.webApp,
      loadWebApp: mocks.loadWebApp,
    }),
    useGetAppConversations: () => ({
      loading: ref(false),
      pinned_conversations: mocks.state.pinnedConversations,
      unpinned_conversations: mocks.state.unpinnedConversations,
      loadWebAppConversations: mocks.loadWebAppConversations,
    }),
    useWebAppChat: () => ({
      loading: ref(false),
      handleWebAppChat: mocks.handleWebAppChat,
    }),
    useStopWebAppChat: () => ({
      loading: ref(false),
      handleStopWebAppChat: mocks.handleStopWebAppChat,
    }),
  }
})

vi.mock('@/hooks/use-ai', async () => {
  const { ref } = await import('vue')
  return {
    useGenerateSuggestedQuestions: () => ({
      suggested_questions: ref<string[]>([]),
      handleGenerateSuggestedQuestions: mocks.handleGenerateSuggestedQuestions,
    }),
  }
})

vi.mock('@/hooks/use-chat-image-upload', () => ({
  useChatImageUpload: () => ({
    triggerFileInput: mocks.triggerFileInput,
    handleFileChange: mocks.handleFileChange,
  }),
}))

vi.mock('@/hooks/use-audio', async () => {
  const { ref } = await import('vue')
  return {
    useAudioPlayer: () => ({
      startAudioStream: mocks.startAudioStream,
      stopAudioStream: mocks.stopAudioStream,
    }),
    useAudioToText: () => ({
      loading: ref(false),
      text: ref(''),
      handleAudioToText: mocks.handleAudioToText,
    }),
  }
})

const buttonStub = {
  template: '<button v-bind="$attrs" @click="$emit(\'click\')"><slot /></button>',
}

describe('web-app chat submit failure', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    if (mocks.state.query) {
      mocks.state.query.value = ''
    }
    if (mocks.state.messages) {
      mocks.state.messages.value = []
    }
    if (mocks.state.pinnedConversations) {
      mocks.state.pinnedConversations.value = []
    }
    if (mocks.state.unpinnedConversations) {
      mocks.state.unpinnedConversations.value = []
    }
    mocks.handleWebAppChat.mockRejectedValue(new Error('网络异常'))
  })

  it('removes temporary blank message when chat request fails', async () => {
    const wrapper = shallowMount(WebAppsIndexView, {
      global: {
        stubs: {
          AiMessage: true,
          HumanMessage: true,
          ChatConversationSkeleton: true,
          UpdateNameModal: true,
          DynamicScroller: true,
          DynamicScrollerItem: true,
          'a-button': buttonStub,
          'a-avatar': true,
          'a-empty': true,
          'a-dropdown': true,
          'a-doption': true,
          'a-skeleton': true,
          'a-skeleton-line': true,
          'a-tooltip': true,
          'icon-edit': true,
          'icon-message': true,
          'icon-more': true,
          'icon-plus': true,
          'icon-voice': true,
          'icon-pause': true,
          'icon-send': true,
          'icon-loading': true,
          'icon-close': true,
          'icon-empty': true,
          'icon-poweroff': true,
        },
      },
    })

    await flushPromises()

    const textarea = wrapper.find('textarea')
    expect(textarea.exists()).toBe(true)
    await textarea.setValue('你好')

    const sendButton = wrapper.find('button[aria-label="发送消息"]')
    expect(sendButton.exists()).toBe(true)
    await sendButton.trigger('click')
    await flushPromises()

    expect(mocks.handleWebAppChat).toHaveBeenCalledWith(
      'token-1',
      expect.objectContaining({
        query: '你好',
        conversation_id: '',
        image_urls: [],
      }),
      expect.any(Function),
    )
    expect(mocks.state.messages?.value).toEqual([])
    expect(mocks.state.query?.value).toBe('你好')
  })
})
