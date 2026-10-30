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
  messageError: vi.fn(),
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
    error: mocks.messageError,
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
    submitLoading: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'submit', 'clear'],
  template: '<button @click="$emit(\'submit\')">send</button>',
})
let mountedWrapper: ReturnType<typeof shallowMount> | undefined

const mountPreview = () => (mountedWrapper = shallowMount(PublicPreviewDebugChat, {
  props: { app: {}, suggested_after_answer: { enable: true }, opening_statement: '', opening_questions: [], text_to_speech: { enable: false } },
  global: { stubs: { ChatComposer: chatComposerStub, ChatConversationSkeleton: true, ChatMessageTimeline: defineComponent({ name: 'ChatMessageTimeline', props: { messages: Array }, template: '<div />' }), HumanMessage: true, 'a-avatar': true } },
}))

const beginStream = (wrapper: ReturnType<typeof shallowMount>, query: string) => {
  let finish!: () => void; let fail!: (error: Error) => void; let event!: (value: unknown) => void
  const pending = new Promise<void>((resolve, reject) => { finish = resolve; fail = reject })
  mocks.sendPublicAppA2aMessage.mockImplementationOnce((...args: unknown[]) => { event = args[4] as typeof event; return pending })
  mocks.queryRef!.value = query
  wrapper.getComponent(chatComposerStub).vm.$emit('submit')
  return { finish, fail, emit: (id: string) => event({ event: 'agent_message', data: { message_id: id, conversation_id: id } }) }
}

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
    firstEvent({ event: 'agent_message', data: { message_id: 'normal', conversation_id: 'conversation-a' } })
    expect(window.localStorage.getItem('public-apps:debug-context:app-1:account-1')).toBe('conversation-a')
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

  it('clears old context and ignores callbacks after clear and unmount', async () => {
    const wrapper = mountPreview()
    const cleared = beginStream(wrapper, 'clear me')
    await flushPromises()
    wrapper.getComponent(chatComposerStub).vm.$emit('clear')
    cleared.emit('stale-after-clear')
    cleared.finish()
    expect(window.localStorage.getItem('public-apps:debug-context:app-1:account-1')).toBeNull()
    const late = beginStream(wrapper, 'late')
    await flushPromises()
    const staleMessage = wrapper.findComponent({ name: 'ChatMessageTimeline' }).props('messages')[0] as { id: string }
    wrapper.unmount()
    mocks.routeProxy!.query = { conversation_id: 'new-context' }
    const remounted = mountPreview()
    await flushPromises()
    late.emit('stale-after-unmount')
    late.finish()
    expect([window.localStorage.getItem('public-apps:debug-context:app-1:account-1'), staleMessage.id]).toEqual(['new-context', ''])
    const sends = mocks.sendPublicAppA2aMessage.mock.calls.length
    mocks.queryRef!.value = 'unmount before nextTick'
    remounted.getComponent(chatComposerStub).vm.$emit('submit')
    remounted.unmount()
    await flushPromises()
    expect(mocks.sendPublicAppA2aMessage).toHaveBeenCalledTimes(sends)
  })

  it('does not let a stale failure clear the replacement session loading state', async () => {
    const wrapper = mountPreview()
    const old = beginStream(wrapper, 'old session')
    await flushPromises()
    mocks.routeProxy!.query = { conversation_id: 'replacement' }
    await flushPromises()
    const current = beginStream(wrapper, 'new session')
    await flushPromises()
    old.fail(new Error('stale failure'))
    await flushPromises()
    expect(mocks.messageError).not.toHaveBeenCalled()
    expect(wrapper.getComponent(chatComposerStub).props('submitLoading')).toBe(true)
    current.finish()
    await flushPromises()
    expect(wrapper.getComponent(chatComposerStub).props('submitLoading')).toBe(false)
  })
})
