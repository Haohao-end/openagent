import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, reactive } from 'vue'

import HomeView from '@/views/pages/HomeView.vue'

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
  loadAssistantAgentCapabilities: vi.fn(),
  loadAssistantAgentMessages: vi.fn(),
  loadAssistantAgentConversations: vi.fn(),
  handleAudioToText: vi.fn(),
  queryRef: undefined as any,
  messagesRef: undefined as any,
  conversationNameRef: undefined as any,
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
  if (!mocks.queryRef) {
    mocks.queryRef = ref('')
  }
  return {
    useChatQueryInput: () => ({
      query: mocks.queryRef,
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
  if (!mocks.messagesRef) {
    mocks.messagesRef = ref([])
  }
  return {
    useAssistantAgentChat: () => ({
      loading: ref(false),
      handleAssistantAgentChat: mocks.handleAssistantAgentChat,
    }),
    useGetAssistantAgentCapabilities: () => ({
      loading: ref(false),
      capabilities: ref({
        image_input: { enabled: false },
      }),
      loadAssistantAgentCapabilities: mocks.loadAssistantAgentCapabilities,
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
      messages: mocks.messagesRef,
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

vi.mock('@/hooks/use-conversation', async () => {
  const { ref } = await import('vue')
  if (!mocks.conversationNameRef) {
    mocks.conversationNameRef = ref('')
  }
  return {
    useGetConversationName: () => ({
      loading: ref(false),
      name: mocks.conversationNameRef,
      loadConversationName: vi.fn(async (conversationId: string) => {
        if (conversationId === 'conversation-1') {
          mocks.conversationNameRef.value = '历史会话 A'
        } else {
          mocks.conversationNameRef.value = '历史会话 B'
        }
      }),
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

const chatComposerStub = defineComponent({
  name: 'ChatComposer',
  props: {
    modelValue: { type: String, default: '' },
    deepThinkingEnabled: { type: Boolean, default: false },
    showUploadButton: { type: Boolean, default: false },
    showImagePreviews: { type: Boolean, default: false },
    uploadDisabled: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'update:deepThinkingEnabled', 'submit'],
  template: `
    <div>
      <textarea
        :value="modelValue"
        @input="$emit('update:modelValue', $event.target.value)"
      />
      <button
        type="button"
        aria-label="切换深度思考"
        @click="$emit('update:deepThinkingEnabled', !deepThinkingEnabled)"
      >
        深度思考
      </button>
      <button type="button" aria-label="发送消息" @click="$emit('submit')">发送消息</button>
    </div>
  `,
})

describe('HomeView deep thinking submit', () => {
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
    mocks.loadAssistantAgentCapabilities.mockResolvedValue(undefined)
    mocks.loadAssistantAgentMessages.mockResolvedValue(undefined)
    mocks.loadAssistantAgentConversations.mockResolvedValue(undefined)
    mocks.handleGenerateAssistantAgentIntroduction.mockResolvedValue(undefined)
    mocks.handleAssistantAgentChat.mockResolvedValue(undefined)
    if (mocks.queryRef) {
      mocks.queryRef.value = ''
    }
    if (mocks.messagesRef) {
      mocks.messagesRef.value = []
    }
    if (mocks.conversationNameRef) {
      mocks.conversationNameRef.value = ''
    }
  })

  it('passes enable_deep_thinking to assistant agent chat when toggle is enabled', async () => {
    const wrapper = shallowMount(HomeView, {
      global: {
        stubs: {
          AiDynamicBackground: componentStub,
          AiMessage: componentStub,
          ChatComposer: chatComposerStub,
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

    const composer = wrapper.getComponent(chatComposerStub)
    expect(composer.props('showUploadButton')).toBe(true)
    expect(composer.props('showImagePreviews')).toBe(true)
    expect(composer.props('uploadDisabled')).toBe(false)

    await wrapper.find('textarea').setValue('帮我整理需求')
    await wrapper.find('button[aria-label="切换深度思考"]').trigger('click')
    await wrapper.find('button[aria-label="发送消息"]').trigger('click')
    await flushPromises()

    expect(mocks.handleAssistantAgentChat).toHaveBeenCalledWith(
      '帮我整理需求',
      [],
      '',
      expect.any(Function),
      true,
    )
  })

  it('renders the current conversation header when a conversation id is provided', async () => {
    mocks.route.fullPath = '/home?conversation_id=conversation-1'
    mocks.route.query = { conversation_id: 'conversation-1' }
    mocks.messagesRef.value = [
      {
        id: 'message-1',
        render_id: 'message-1',
        query: '你好',
        image_urls: [],
        agent_thoughts: [],
        answer: '你好',
        answer_parts: [],
        artifacts: [],
        suggested_questions: [],
        created_at: 1717526400,
      },
    ] as any

    const wrapper = shallowMount(HomeView, {
      global: {
        stubs: {
          AiDynamicBackground: componentStub,
          AiMessage: componentStub,
          ChatComposer: chatComposerStub,
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

    expect(mocks.loadAssistantAgentMessages).toHaveBeenCalled()
    expect(mocks.conversationNameRef.value).toBe('历史会话 A')
    expect(wrapper.text()).toContain('历史会话 A')
    expect(wrapper.text()).not.toContain('当前会话')
    expect(wrapper.text()).not.toContain('会话 ID')
  })

  it('ignores a stream event after switching to another conversation', async () => {
    mocks.route.query = { conversation_id: 'conversation-a' }
    mocks.route.fullPath = '/home?conversation_id=conversation-a'
    mocks.messagesRef.value = [{ id: 'history-a', conversation_id: 'conversation-a', query: 'A', answer: 'history A', agent_thoughts: [] }] as any
    let emitStreamEvent: ((event: any) => void) | undefined
    let resolveStream: (() => void) | undefined
    mocks.handleAssistantAgentChat.mockImplementation((_query, _images, _conversation, onEvent) => {
      emitStreamEvent = onEvent
      return new Promise<void>((resolve) => { resolveStream = resolve })
    })

    const wrapper = shallowMount(HomeView, {
      global: {
        stubs: {
          AiDynamicBackground: componentStub,
          AiMessage: componentStub,
          ChatComposer: chatComposerStub,
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

    mocks.queryRef.value = 'question from A'
    const submitPromise = (wrapper.vm.$ as any).setupState.handleSubmit()
    await flushPromises()
    expect(emitStreamEvent).toBeDefined()

    mocks.messagesRef.value = [{ id: 'history-b', conversation_id: 'conversation-b', query: 'B', answer: 'history B', agent_thoughts: [] }] as any
    mocks.route.query = { conversation_id: 'conversation-b' }
    mocks.route.fullPath = '/home?conversation_id=conversation-b'
    await flushPromises()

    emitStreamEvent!({ event: 'agent_message', data: { message_id: 'late-a', task_id: 'task-a', conversation_id: 'conversation-a', thought: 'stale A' } })

    expect(mocks.messagesRef.value[0].id).toBe('history-b')
    expect(mocks.messagesRef.value[0].answer).toBe('history B')
    expect(mocks.route.query.conversation_id).toBe('conversation-b')

    resolveStream?.()
    await submitPromise
    wrapper.unmount()
  })
})
