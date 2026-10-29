import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'

import PublicPreviewDebugChat from '@/views/store/public-apps/components/PublicPreviewDebugChat.vue'

const mocks = vi.hoisted(() => ({
  route: {
    params: { app_id: 'app-1' },
    query: {},
  } as any,
  routeProxy: null as null | { params: { app_id: string }; query: Record<string, string> },
  queryRef: null as null | { value: string },
  getPublicAppA2aConversationMessages: vi.fn().mockResolvedValue({
    data: [],
  }),
  sendPublicAppA2aMessage: vi.fn().mockResolvedValue(undefined),
  triggerFileInput: vi.fn(),
  handleFileChange: vi.fn(),
  uploadImage: vi.fn(),
}))

vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  mocks.routeProxy = reactive(mocks.route)
  return { useRoute: () => mocks.routeProxy }
})

vi.mock('@/stores/account', () => ({
  useAccountStore: () => ({
    account: {
      id: 'account-1',
      name: 'Tester',
      avatar: '',
    },
  }),
}))

vi.mock('@/hooks/use-chat-query-input', async () => {
  const { ref } = await import('vue')
  if (!mocks.queryRef) {
    mocks.queryRef = ref('')
  }
  return {
    useChatQueryInput: () => ({
      query: mocks.queryRef,
      queryTextareaRef: ref<HTMLTextAreaElement | null>(null),
      adjustQueryTextareaHeight: vi.fn(),
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
    useAudioToText: () => ({
      loading: ref(false),
    }),
  }
})

vi.mock('@/services/public-app', () => ({
  getPublicAppA2aConversationMessages: mocks.getPublicAppA2aConversationMessages,
  sendPublicAppA2aMessage: mocks.sendPublicAppA2aMessage,
}))

vi.mock('@/services/upload-file', () => ({
  uploadImage: mocks.uploadImage,
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

const chatComposerStub = defineComponent({
  name: 'ChatComposer',
  props: {
    modelValue: { type: String, default: '' },
    showUploadButton: { type: Boolean, default: false },
    showImagePreviews: { type: Boolean, default: false },
    uploadDisabled: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'submit'],
  template: '<button @click="$emit(\'submit\')">send</button>',
})
let mountedWrapper: ReturnType<typeof shallowMount> | undefined

describe('PublicPreviewDebugChat', () => {
  afterEach(() => {
    mountedWrapper?.unmount()
    mountedWrapper = undefined
  })

  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getPublicAppA2aConversationMessages.mockResolvedValue({ data: [] })
    if (mocks.routeProxy) {
      mocks.routeProxy.params.app_id = 'app-1'
      mocks.routeProxy.query = {}
    }
    if (mocks.queryRef) {
      mocks.queryRef.value = ''
    }
  })

  it('renders the upload entry in disabled state for public preview', async () => {
    const wrapper = shallowMount(PublicPreviewDebugChat, {
      props: {
        app: {
          draft_app_config: {
            capabilities: {
              image_input: { enabled: false },
            },
          },
        },
        suggested_after_answer: { enable: true },
        opening_statement: '',
        opening_questions: [],
        text_to_speech: { enable: false },
      },
      global: {
        stubs: {
          ChatComposer: chatComposerStub,
          ChatConversationSkeleton: true,
          ChatMessageTimeline: true,
          HumanMessage: true,
          'a-avatar': true,
        },
      },
    })
    mountedWrapper = wrapper

    await flushPromises()

    const composer = wrapper.getComponent(chatComposerStub)
    expect(composer.props('showUploadButton')).toBe(true)
    expect(composer.props('showImagePreviews')).toBe(true)
    expect(composer.props('uploadDisabled')).toBe(true)
  })

  it('ignores stale history and stream responses after switching conversations', async () => {
    mocks.routeProxy!.query = { conversation_id: 'conversation-a' }
    let finishHistoryA!: (value: { data: Array<Record<string, unknown>> }) => void
    const historyA = new Promise<{ data: Array<Record<string, unknown>> }>((resolve) => { finishHistoryA = resolve })
    mocks.getPublicAppA2aConversationMessages.mockImplementation((_app: string, id: string) => id === 'conversation-a' ? historyA : Promise.resolve({ data: [{ id: 'message-b', conversation_id: 'conversation-b', query: 'history-b' }] }))
    let finishFirst!: () => void
    let firstEvent!: (event: unknown) => void
    const firstStream = new Promise<void>((resolve) => { finishFirst = resolve })
    mocks.sendPublicAppA2aMessage.mockImplementationOnce((...args: unknown[]) => {
      firstEvent = args[4] as typeof firstEvent
      return firstStream
    })
    const wrapper = shallowMount(PublicPreviewDebugChat, {
      props: {
        app: {},
        suggested_after_answer: { enable: true },
        opening_statement: '',
        opening_questions: [],
        text_to_speech: { enable: false },
      },
      global: { stubs: { ChatComposer: chatComposerStub, ChatConversationSkeleton: true, ChatMessageTimeline: defineComponent({ props: { messages: Array }, template: '<div>{{ messages[0]?.query }}</div>' }), HumanMessage: true, 'a-avatar': true } },
    })
    mountedWrapper = wrapper
    await flushPromises()
    const composer = wrapper.getComponent(chatComposerStub)
    composer.vm.$emit('update:modelValue', 'first')
    composer.vm.$emit('submit')
    await flushPromises()
    mocks.routeProxy!.query = { conversation_id: 'conversation-b' }
    await flushPromises()
    firstEvent({ event: 'agent_message', data: { message_id: 'message-a', conversation_id: 'conversation-a' } })
    finishFirst()
    finishHistoryA({ data: [{ id: 'message-a', conversation_id: 'conversation-a', query: 'history-a' }] })
    await flushPromises()
    expect(wrapper.text()).toContain('history-b')
    expect(wrapper.text()).not.toContain('history-a')
    composer.vm.$emit('update:modelValue', 'follow-up')
    composer.vm.$emit('submit')
    await flushPromises()
    expect(mocks.sendPublicAppA2aMessage.mock.calls[1][2]).toBe('conversation-b')
  })
})
