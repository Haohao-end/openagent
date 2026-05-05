import { flushPromises, shallowMount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import HomeView from '@/views/pages/HomeView.vue'
import { HOME_NEW_CONVERSATION_QUERY_KEY } from '@/views/pages/home-new-conversation'

const mocks = vi.hoisted(() => ({
  route: undefined as any,
  routerReplace: vi.fn(),
  routerPush: vi.fn(),
  loadHomeIntent: vi.fn(),
  loadCurrentUser: vi.fn(),
  handleGenerateSuggestedQuestions: vi.fn(),
  handleGenerateAssistantAgentIntroduction: vi.fn(),
  handleAssistantAgentChat: vi.fn(),
  handleStopAssistantAgentChat: vi.fn(),
  handleDeleteAssistantAgentConversation: vi.fn(),
  loadAssistantAgentMessages: vi.fn(),
  loadAssistantAgentConversations: vi.fn(),
  handleAudioToText: vi.fn(),
}))

vi.mock('vue-router', () => ({
  createRouter: vi.fn(() => ({
    beforeEach: vi.fn(),
  })),
  createWebHistory: vi.fn(),
  useRoute: () => mocks.route,
  useRouter: () => ({
    push: mocks.routerPush,
    replace: mocks.routerReplace,
  }),
}))

vi.mock('@/stores/account', () => ({
  useAccountStore: () => ({
    account: { name: 'tester', avatar: '' },
    update: vi.fn(),
    clear: vi.fn(),
  }),
}))

vi.mock('@/stores/credential', () => ({
  useCredentialStore: () => ({
    credential: { access_token: 'token', expire_at: 4102444800 },
  }),
}))

vi.mock('@/utils/auth', () => ({
  isCredentialLoggedIn: () => true,
}))

vi.mock('@/utils/storage', () => ({
  default: {
    get: vi.fn((_key: string, fallback: unknown) => fallback),
    set: vi.fn(),
    remove: vi.fn(),
    clear: vi.fn(),
  },
}))

vi.mock('@/hooks/use-home', async () => {
  const { ref } = await import('vue')
  return {
    useGetHomeIntent: () => ({
      loading: ref(false),
      loadHomeIntent: mocks.loadHomeIntent,
    }),
  }
})

vi.mock('@/hooks/use-account', async () => {
  const { ref } = await import('vue')
  return {
    useGetCurrentUser: () => ({
      current_user: ref({ id: 'user-1', name: 'tester' }),
      loadCurrentUser: mocks.loadCurrentUser,
    }),
  }
})

vi.mock('@/hooks/use-ai', async () => {
  const { ref } = await import('vue')
  return {
    useGenerateSuggestedQuestions: () => ({
      suggested_questions: ref([]),
      handleGenerateSuggestedQuestions: mocks.handleGenerateSuggestedQuestions,
    }),
  }
})

vi.mock('@/hooks/use-chat-query-input', async () => {
  const { ref } = await import('vue')
  return {
    useChatQueryInput: () => ({
      query: ref(''),
      queryTextareaRef: ref(null),
      adjustQueryTextareaHeight: vi.fn(),
      restoreQueryDraft: vi.fn(),
    }),
  }
})

vi.mock('@/hooks/use-chat-image-upload', () => ({
  useChatImageUpload: () => ({
    triggerFileInput: vi.fn(),
    handleFileChange: vi.fn(),
  }),
}))

vi.mock('@/hooks/use-assistant-agent', async () => {
  const { ref } = await import('vue')
  return {
    useAssistantAgentChat: () => ({
      loading: ref(false),
      handleAssistantAgentChat: mocks.handleAssistantAgentChat,
    }),
    useGenerateAssistantAgentIntroduction: () => ({
      loading: ref(false),
      handleGenerateAssistantAgentIntroduction: mocks.handleGenerateAssistantAgentIntroduction,
    }),
    useDeleteAssistantAgentConversation: () => ({
      loading: ref(false),
      handleDeleteAssistantAgentConversation: mocks.handleDeleteAssistantAgentConversation,
    }),
    useGetAssistantAgentMessagesWithPage: () => ({
      loading: ref(false),
      messages: ref([]),
      loadAssistantAgentMessages: mocks.loadAssistantAgentMessages,
    }),
    useStopAssistantAgentChat: () => ({
      loading: ref(false),
      handleStopAssistantAgentChat: mocks.handleStopAssistantAgentChat,
    }),
    useGetAssistantAgentConversations: () => ({
      loading: ref(false),
      conversations: ref([]),
      loadAssistantAgentConversations: mocks.loadAssistantAgentConversations,
    }),
  }
})

vi.mock('@/hooks/use-audio', async () => {
  const { ref } = await import('vue')
  return {
    useAudioToText: () => ({
      loading: ref(false),
      text: ref(''),
      handleAudioToText: mocks.handleAudioToText,
    }),
    useAudioPlayer: () => ({
      stopAudioStream: vi.fn(),
    }),
  }
})

vi.mock('@/services/upload-file', () => ({
  uploadImage: vi.fn(),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('js-audio-recorder', () => ({
  default: vi.fn(),
}))

const componentStub = {
  template: '<div />',
}

describe('HomeView sidebar new conversation request', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route = reactive({
      path: '/home',
      fullPath: '/home',
      query: {} as Record<string, unknown>,
      params: {} as Record<string, unknown>,
    })
    mocks.loadHomeIntent.mockResolvedValue({
      intent: '继续探索你的需求',
      confidence: 0.8,
      suggested_actions: [{ label: '继续聊', action: 'view_capabilities', icon: 'help' }],
      is_default: false,
    })
    mocks.loadCurrentUser.mockResolvedValue(undefined)
    mocks.loadAssistantAgentMessages.mockResolvedValue(undefined)
    mocks.handleDeleteAssistantAgentConversation.mockResolvedValue(undefined)
  })

  it('does not reload intent or clear backend conversation when empty home is already loaded', async () => {
    shallowMount(HomeView, {
      global: {
        stubs: {
          AiDynamicBackground: componentStub,
          AiMessage: componentStub,
          ChatComposer: componentStub,
          HumanMessage: componentStub,
          ChatConversationSkeleton: componentStub,
          LoginModal: componentStub,
          'a-button': componentStub,
          'icon-down': componentStub,
          'icon-poweroff': componentStub,
        },
      },
    })
    await flushPromises()

    expect(mocks.loadAssistantAgentMessages).toHaveBeenCalledTimes(1)
    expect(mocks.loadHomeIntent).toHaveBeenCalledTimes(1)
    expect(mocks.handleDeleteAssistantAgentConversation).not.toHaveBeenCalled()

    mocks.route.query = {
      [HOME_NEW_CONVERSATION_QUERY_KEY]: '1710835200000',
    }
    await flushPromises()

    expect(mocks.handleDeleteAssistantAgentConversation).not.toHaveBeenCalled()
    expect(mocks.loadAssistantAgentMessages).toHaveBeenCalledTimes(1)
    expect(mocks.loadHomeIntent).toHaveBeenCalledTimes(1)
    expect(mocks.routerReplace).toHaveBeenCalledWith({
      path: '/home',
      query: {},
    })
  })
})
