import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { nextTick, reactive, ref } from 'vue'

import PreviewDebugChat from '../PreviewDebugChat.vue'

const mocks = vi.hoisted(() => ({
  route: {
    params: { app_id: 'app-1' },
    query: {},
    fullPath: '/space/apps/app-1',
  } as Record<string, any>,
  replace: vi.fn().mockResolvedValue(undefined),
  query: { value: '' },
  suggestedQuestions: { value: [] as string[] },
  messages: { value: [] as Record<string, any>[] },
  targetVisible: { value: false } as { value: boolean },
  paginator: {
    value: {
      current_page: 1,
      page_size: 5,
      total_page: 0,
      total_record: 0,
    },
  },
  debugChatLoading: { value: false },
  deleteDebugConversationLoading: { value: false },
  getDebugConversationMessagesWithPageLoading: { value: false },
  stopDebugChatLoading: { value: false },
  audioToTextLoading: { value: false },
  audioText: { value: '' },
  audioSuccess: vi.fn(),
  isRecording: { value: false },
  uploadFileLoading: { value: false },
  handleDebugChat: vi.fn().mockResolvedValue(undefined),
  handleDeleteDebugConversation: vi.fn().mockResolvedValue(undefined),
  loadDebugConversationMessages: vi.fn().mockResolvedValue(undefined),
  handleStopDebugChat: vi.fn().mockResolvedValue(undefined),
  handleGenerateSuggestedQuestions: vi.fn().mockResolvedValue(undefined),
  handleAudioToText: vi.fn().mockResolvedValue(undefined),
  triggerFileInput: vi.fn(),
  handleFileChange: vi.fn(),
  adjustQueryTextareaHeight: vi.fn(),
  restoreQueryDraft: vi.fn(),
  startAudioStream: vi.fn(),
  stopAudioStream: vi.fn(),
  scrollToBottom: vi.fn(),
  scrollToItem: vi.fn(),
}))

let scrollIntoViewSpy: ReturnType<typeof vi.fn>

const dynamicScrollerStub = {
  props: ['items', 'keyField'],
  template:
    '<div class="dynamic-scroller-stub" :data-key-field="keyField"><template v-for="(item, index) in items" :key="item.render_id || item.id || index"><slot :item="item" :active="true" /></template></div>',
  methods: {
    scrollToBottom() {
      mocks.scrollToBottom()
    },
    scrollToItem(index: number) {
      mocks.scrollToItem(index)
      if (mocks.scrollToItem.mock.calls.length >= 2) {
        mocks.targetVisible.value = true
      }
    },
  },
}

const dynamicScrollerItemStub = {
  props: ['item', 'active', 'sizeDependencies'],
  template:
    '<div class="vue-recycle-scroller__item-view" style="transform: translateY(0px) translateX(0px);"><div class="dynamic-scroller-item-stub" :data-index="item.id" :data-size-dependencies="JSON.stringify(sizeDependencies)"><slot /></div></div>',
}

const dynamicScrollerItemNoTargetStub = {
  inheritAttrs: false,
  props: ['item', 'active', 'sizeDependencies'],
  template:
    '<div class="dynamic-scroller-item-stub-no-target" :data-size-dependencies="JSON.stringify(sizeDependencies)"><slot /></div>',
}

const dynamicScrollerItemHiddenTargetStub = {
  props: ['item', 'active', 'sizeDependencies'],
  setup() {
    return {
      targetVisible: mocks.targetVisible,
      targetId: 'older-message-1',
    }
  },
  template:
    '<div class="vue-recycle-scroller__item-view" :style="item.id === targetId && !targetVisible ? \'transform: translateY(-9999px) translateX(0px);\' : \'transform: translateY(0px) translateX(0px);\'"><div class="dynamic-scroller-item-stub-hidden-target" :data-index="item.id" :data-size-dependencies="JSON.stringify(sizeDependencies)"><slot /></div></div>',
}

vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  return { useRoute: () => reactive(mocks.route), useRouter: () => ({ replace: mocks.replace }) }
})

vi.mock('@/hooks/use-chat-query-input', () => ({
  useChatQueryInput: () => ({
    query: mocks.query,
    queryTextareaRef: ref<HTMLTextAreaElement | null>(null),
    adjustQueryTextareaHeight: mocks.adjustQueryTextareaHeight,
    restoreQueryDraft: mocks.restoreQueryDraft,
  }),
}))

vi.mock('@/hooks/use-chat-image-upload', () => ({
  useChatImageUpload: () => ({
    triggerFileInput: mocks.triggerFileInput,
    handleFileChange: mocks.handleFileChange,
  }),
}))

vi.mock('@/hooks/use-audio', () => ({
  useAudioToText: () => ({
    loading: mocks.audioToTextLoading,
    text: mocks.audioText,
    handleAudioToText: mocks.handleAudioToText,
  }),
  useAudioPlayer: () => ({
    startAudioStream: mocks.startAudioStream,
    stopAudioStream: mocks.stopAudioStream,
  }),
}))

vi.mock('@/hooks/use-ai', () => ({
  useGenerateSuggestedQuestions: () => ({
    suggested_questions: mocks.suggestedQuestions,
    handleGenerateSuggestedQuestions: mocks.handleGenerateSuggestedQuestions,
    clearSuggestedQuestions: vi.fn(),
  }),
}))

vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')

  mocks.messages = ref<Record<string, any>[]>([])

  return {
    useDebugChat: () => ({
      loading: mocks.debugChatLoading,
      handleDebugChat: mocks.handleDebugChat,
    }),
    useDeleteDebugConversation: () => ({
      loading: mocks.deleteDebugConversationLoading,
      handleDeleteDebugConversation: mocks.handleDeleteDebugConversation,
    }),
    useGetDebugConversationMessagesWithPage: () => ({
      loading: mocks.getDebugConversationMessagesWithPageLoading,
      messages: mocks.messages,
      paginator: mocks.paginator,
      loadDebugConversationMessages: mocks.loadDebugConversationMessages,
    }),
    useStopDebugChat: () => ({
      loading: mocks.stopDebugChatLoading,
      handleStopDebugChat: mocks.handleStopDebugChat,
    }),
  }
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

vi.mock('@/services/upload-file', () => ({
  uploadImage: vi.fn(),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    error: vi.fn(),
    success: mocks.audioSuccess,
    warning: vi.fn(),
  },
}))

describe('PreviewDebugChat', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0)
      return 0
    })
    scrollIntoViewSpy = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoViewSpy,
    })
    mocks.route.query = {}
    mocks.route.params = { app_id: 'app-1' }
    mocks.query.value = ''
    mocks.suggestedQuestions.value = []
    mocks.messages.value = []
    mocks.targetVisible = ref(false) as any
    mocks.paginator.value = {
      current_page: 1,
      page_size: 5,
      total_page: 0,
      total_record: 0,
    }
    mocks.debugChatLoading.value = false
    mocks.deleteDebugConversationLoading.value = false
    mocks.getDebugConversationMessagesWithPageLoading.value = false
    mocks.stopDebugChatLoading.value = false
    mocks.audioToTextLoading.value = false
    mocks.audioText.value = ''
    mocks.isRecording.value = false
    mocks.uploadFileLoading.value = false
  })

  it('renders the light dynamic glass container for app debug chat', async () => {
    const wrapper = shallowMount(PreviewDebugChat, {
      global: {
        stubs: {
          'scroll-navigator': {
            template: '<div class="scroll-navigator-stub"><slot /></div>',
          },
          'chat-composer': true,
          'chat-conversation-skeleton': true,
          'dynamic-scroller': dynamicScrollerStub,
          'dynamic-scroller-item': dynamicScrollerItemStub,
          'human-message': true,
          'ai-message': true,
          'a-avatar': true,
          'a-button': true,
          'icon-poweroff': true,
          AiDynamicBackground: {
            template: '<div class="ai-dynamic-background-stub"></div>',
          },
        },
      },
      props: {
        app: {
          name: 'OpenAgent',
          icon: '',
        },
        suggested_after_answer: { enable: true },
        opening_statement: '',
        opening_questions: [],
        capabilities: {},
        text_to_speech: {
          enable: false,
          auto_play: false,
          voice: 'alex',
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('.space-apps-debug-chat').exists()).toBe(true)
    expect(wrapper.find('.space-apps-debug-chat__ambient').exists()).toBe(true)
    expect(wrapper.find('.space-apps-debug-chat__veil').exists()).toBe(true)
    expect(wrapper.find('.space-apps-debug-chat__surface').exists()).toBe(true)
  })

  it('wires layout-sensitive size dependencies into the virtual scroller items', async () => {
    const wrapper = shallowMount(PreviewDebugChat, {
      global: {
        stubs: {
          'scroll-navigator': {
            template: '<div class="scroll-navigator-stub"><slot /></div>',
          },
          'chat-composer': true,
          'chat-conversation-skeleton': true,
          'dynamic-scroller': dynamicScrollerStub,
          'dynamic-scroller-item': dynamicScrollerItemStub,
          'human-message': true,
          'ai-message': true,
          'a-avatar': true,
          'a-button': true,
          'icon-poweroff': true,
          AiDynamicBackground: {
            template: '<div class="ai-dynamic-background-stub"></div>',
          },
        },
      },
      props: {
        app: {
          name: 'OpenAgent',
          icon: '',
        },
        suggested_after_answer: { enable: true },
        opening_statement: '',
        opening_questions: [],
        capabilities: {},
        text_to_speech: {
          enable: false,
          auto_play: false,
          voice: 'alex',
        },
      },
    })

    await flushPromises()
    mocks.messages.value = [
      {
        id: 'message-1',
        render_id: 'render-message-1',
        conversation_id: 'conversation-1',
        query: '请总结这张图',
        image_urls: ['https://example.com/image-a.png'],
        input_parts: [],
        answer: '第一版回答',
        answer_parts: [{ type: 'text', text: '第一版回答' }],
        artifacts: [{ name: 'plan.docx', url: 'https://example.com/plan.docx' }],
        callable_trace_events: [
          { event_id: 'trace-1', run_id: 'run-1', phase: 'start', inputs: { prompt: 'trace' } },
        ],
        total_token_count: 12,
        latency: 1.2,
        agent_thoughts: [
          {
            id: 'thought-1',
            event: 'deepStep',
            thought: '正在整理步骤',
            observation: '',
            tool: 'write_todos',
            tool_input: {
              timeline: {
                title: '整理步骤',
              },
            },
            latency: 1,
            created_at: 0,
          },
        ],
        created_at: 1710000000,
        suggested_questions: ['继续'],
      },
    ]
    await flushPromises()
    await nextTick()

    const scrollerItem = wrapper.get('.dynamic-scroller-item-stub')
    const sizeDependencies = JSON.parse(scrollerItem.attributes('data-size-dependencies') || '[]')

    expect(wrapper.get('.dynamic-scroller-stub').attributes('data-key-field')).toBe('render_id')
    expect(sizeDependencies).toHaveLength(9)
    expect(sizeDependencies[0]).toBe('请总结这张图')
    expect(sizeDependencies[1]).toContain('https://example.com/image-a.png')
    expect(sizeDependencies[2]).toBe('第一版回答')
    expect(sizeDependencies[4]).toContain('plan.docx')
    expect(sizeDependencies[5]).toContain('正在整理步骤')
    expect(sizeDependencies[6]).not.toContain('trace')
    expect(sizeDependencies[7]).toContain('继续')
    expect(sizeDependencies[8]).toBe(0)
  })

  it('loads older pages until the route message becomes available', async () => {
    mocks.route.query = {
      conversation_id: 'conversation-1',
      message_id: 'older-message-1',
    }

    mocks.loadDebugConversationMessages.mockImplementation(
      async (_appId: string, init: boolean, conversationId: string) => {
        expect(conversationId).toBe('conversation-1')

        if (init) {
          mocks.paginator.value = {
            current_page: 2,
            page_size: 5,
            total_page: 2,
            total_record: 4,
          }
          mocks.messages.value = [
            {
              id: 'latest-message-2',
              render_id: 'latest-message-2',
              conversation_id: 'conversation-1',
              query: '最新问题 2',
              image_urls: [],
              input_parts: [],
              answer: '最新回答 2',
              answer_parts: [{ type: 'text', text: '最新回答 2' }],
              artifacts: [],
              total_token_count: 2,
              latency: 1.2,
              agent_thoughts: [],
              created_at: 1710000002,
              suggested_questions: [],
            },
            {
              id: 'latest-message-1',
              render_id: 'latest-message-1',
              conversation_id: 'conversation-1',
              query: '最新问题 1',
              image_urls: [],
              input_parts: [],
              answer: '最新回答 1',
              answer_parts: [{ type: 'text', text: '最新回答 1' }],
              artifacts: [],
              total_token_count: 1,
              latency: 1.1,
              agent_thoughts: [],
              created_at: 1710000001,
              suggested_questions: [],
            },
          ]
          return
        }

        mocks.paginator.value = {
          current_page: 3,
          page_size: 5,
          total_page: 2,
          total_record: 4,
        }
        mocks.messages.value.push(
          {
            id: 'older-message-2',
            render_id: 'older-message-2',
            conversation_id: 'conversation-1',
            query: '更早问题 2',
            image_urls: [],
            input_parts: [],
            answer: '更早回答 2',
            answer_parts: [{ type: 'text', text: '更早回答 2' }],
            artifacts: [],
            total_token_count: 2,
            latency: 1,
            agent_thoughts: [],
            created_at: 1710000000,
            suggested_questions: [],
          },
          {
            id: 'older-message-1',
            render_id: 'older-message-1',
            conversation_id: 'conversation-1',
            query: '更早问题 1',
            image_urls: [],
            input_parts: [],
            answer: '更早回答 1',
            answer_parts: [{ type: 'text', text: '更早回答 1' }],
            artifacts: [],
            total_token_count: 1,
            latency: 0.9,
            agent_thoughts: [],
            created_at: 1709999999,
            suggested_questions: [],
          },
        )
      },
    )

    const wrapper = shallowMount(PreviewDebugChat, {
      global: {
        stubs: {
          'scroll-navigator': {
            template: '<div class="scroll-navigator-stub"><slot /></div>',
          },
          'chat-composer': true,
          'chat-conversation-skeleton': true,
          'dynamic-scroller': dynamicScrollerStub,
          'dynamic-scroller-item': dynamicScrollerItemStub,
          'human-message': true,
          'ai-message': true,
          'a-avatar': true,
          'a-button': true,
          'icon-poweroff': true,
          AiDynamicBackground: {
            template: '<div class="ai-dynamic-background-stub"></div>',
          },
        },
      },
      props: {
        app: {
          name: 'OpenAgent',
          icon: '',
        },
        suggested_after_answer: { enable: true },
        opening_statement: '',
        opening_questions: [],
        capabilities: {},
        text_to_speech: {
          enable: false,
          auto_play: false,
          voice: 'alex',
        },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(mocks.loadDebugConversationMessages).toHaveBeenCalledTimes(2)
    expect(mocks.loadDebugConversationMessages).toHaveBeenNthCalledWith(
      1,
      'app-1',
      true,
      'conversation-1',
    )
    expect(mocks.loadDebugConversationMessages).toHaveBeenNthCalledWith(
      2,
      'app-1',
      false,
      'conversation-1',
    )
    expect(mocks.scrollToItem).toHaveBeenCalledTimes(1)
    expect(mocks.scrollToItem).toHaveBeenCalledWith(expect.any(Number))
    expect(mocks.scrollToBottom).not.toHaveBeenCalled()
    expect(scrollIntoViewSpy).not.toHaveBeenCalled()
    expect(wrapper.get('.dynamic-scroller-stub').attributes('data-key-field')).toBe('render_id')
  })

  it('keeps retrying until a hidden target recycle item becomes visible', async () => {
    mocks.route.query = {
      conversation_id: 'conversation-1',
      message_id: 'older-message-1',
    }

    mocks.loadDebugConversationMessages.mockImplementation(
      async (_appId: string, init: boolean, conversationId: string) => {
        expect(conversationId).toBe('conversation-1')

        if (init) {
          mocks.paginator.value = {
            current_page: 1,
            page_size: 5,
            total_page: 1,
            total_record: 1,
          }
          mocks.messages.value = [
            {
              id: 'older-message-1',
              render_id: 'older-message-1',
              conversation_id: 'conversation-1',
              query: '更早问题 1',
              image_urls: [],
              input_parts: [],
              answer: '更早回答 1',
              answer_parts: [{ type: 'text', text: '更早回答 1' }],
              artifacts: [],
              total_token_count: 1,
              latency: 0.9,
              agent_thoughts: [],
              created_at: 1709999999,
              suggested_questions: [],
            },
          ]
          return
        }

        mocks.paginator.value = {
          current_page: 1,
          page_size: 5,
          total_page: 1,
          total_record: 1,
        }
      },
    )

    const wrapper = shallowMount(PreviewDebugChat, {
      global: {
        stubs: {
          'scroll-navigator': {
            template: '<div class="scroll-navigator-stub"><slot /></div>',
          },
          'chat-composer': true,
          'chat-conversation-skeleton': true,
          'dynamic-scroller': dynamicScrollerStub,
          'dynamic-scroller-item': dynamicScrollerItemHiddenTargetStub,
          'human-message': true,
          'ai-message': true,
          'a-avatar': true,
          'a-button': true,
          'icon-poweroff': true,
          AiDynamicBackground: {
            template: '<div class="ai-dynamic-background-stub"></div>',
          },
        },
      },
      props: {
        app: {
          name: 'OpenAgent',
          icon: '',
        },
        suggested_after_answer: { enable: true },
        opening_statement: '',
        opening_questions: [],
        capabilities: {},
        text_to_speech: {
          enable: false,
          auto_play: false,
          voice: 'alex',
        },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(mocks.loadDebugConversationMessages).toHaveBeenCalledTimes(1)
    expect(mocks.loadDebugConversationMessages).toHaveBeenNthCalledWith(
      1,
      'app-1',
      true,
      'conversation-1',
    )
    expect(mocks.scrollToItem).toHaveBeenCalledTimes(2)
    expect(mocks.scrollToBottom).not.toHaveBeenCalled()
    expect(mocks.targetVisible.value).toBe(true)
    expect(scrollIntoViewSpy).not.toHaveBeenCalled()
    expect(wrapper.get('.dynamic-scroller-stub').attributes('data-key-field')).toBe('render_id')
  })

  it('ignores a debug stream event after unmount', async () => {
    let onData: ((event: Record<string, any>) => void) | undefined
    let finishStream: (() => void) | undefined
    let streamSignal: AbortSignal | undefined
    mocks.query.value = 'hello'
    mocks.handleDebugChat.mockImplementation(
      (_appId, _query, _images, _conversationId, callback, _deepThinking, signal) => {
        onData = callback
        streamSignal = signal
        return new Promise<void>((resolve) => {
          finishStream = resolve
        })
      },
    )
    const wrapper = shallowMount(PreviewDebugChat, {
      global: {
        stubs: {
          'scroll-navigator': { template: '<div><slot /></div>' },
          'chat-composer': {
            emits: ['submit'],
            template: `<button class="chat-composer-submit" @click="$emit('submit')" />`,
          },
        },
      },
      props: {
        app: { id: 'app-1' },
        suggested_after_answer: { enable: false },
        opening_statement: '',
        opening_questions: [],
      },
    })
    await flushPromises()
    mocks.replace.mockClear()
    wrapper.find('.chat-composer-submit').trigger('click')
    await flushPromises()
    expect(onData).toBeTypeOf('function')
    const pendingMessage = mocks.messages.value[0]

    wrapper.unmount()
    expect(streamSignal?.aborted).toBe(true)
    mocks.route.params = { app_id: 'other-app' }
    onData?.({
      event: 'agent_message',
      data: {
        message_id: 'late-message',
        task_id: 'late-task',
        conversation_id: 'late-conversation',
        thought: 'late',
      },
    })
    await flushPromises()

    expect(mocks.replace).not.toHaveBeenCalled()
    expect(pendingMessage.id).toBe('')
    expect(pendingMessage.answer).toBe('')
    finishStream?.()
    await flushPromises()
  })

  it('does not surface a debug stream rejection after unmount', async () => {
    let rejectStream!: (error: Error) => void
    const errors: unknown[] = []
    mocks.query.value = 'hello'
    mocks.handleDebugChat.mockReturnValueOnce(new Promise((_, reject) => { rejectStream = reject }))
    const wrapper = shallowMount(PreviewDebugChat, {
      global: {
        config: { errorHandler: (error) => errors.push(error) },
        stubs: {
          'scroll-navigator': { template: '<div><slot /></div>' },
          'chat-composer': { emits: ['submit'], template: '<button class="chat-composer-submit" @click="$emit(\'submit\')" />' },
        },
      },
      props: {
        app: { id: 'app-1' },
        suggested_after_answer: { enable: false },
        opening_statement: '',
        opening_questions: [],
      },
    })
    await flushPromises()
    wrapper.find('.chat-composer-submit').trigger('click')
    await flushPromises()
    wrapper.unmount()
    rejectStream(new Error('late debug stream failure'))
    await flushPromises()

    expect(errors).toEqual([])
  })

  it('preserves composer edits made while voice transcription is pending', async () => {
    let finishTranscription!: () => void
    mocks.handleAudioToText.mockImplementationOnce(
      () => new Promise<void>((resolve) => { finishTranscription = resolve }),
    )
    const wrapper = shallowMount(PreviewDebugChat, {
      props: {
        app: { id: 'app-1' },
        suggested_after_answer: { enable: false },
        opening_statement: '',
        opening_questions: [],
      },
    })
    await flushPromises()

    const state = (wrapper.vm.$ as any).setupState
    state.recorder = { stop: vi.fn(), getWAVBlob: () => new Blob(['voice']) }
    const transcriptionPromise = state.handleStopRecord()
    await flushPromises()
    expect(mocks.handleAudioToText).toHaveBeenCalledTimes(1)
    mocks.query.value = 'user edit'
    mocks.audioText.value = 'voice transcription'
    finishTranscription()
    await transcriptionPromise

    expect(mocks.query.value).toBe('user edit')
    wrapper.unmount()
  })

  it('shows one success toast when voice transcription completes', async () => {
    mocks.handleAudioToText.mockImplementationOnce(async () => {
      mocks.audioText.value = 'voice transcription'
      mocks.audioSuccess('hook success')
    })
    const wrapper = shallowMount(PreviewDebugChat, {
      props: {
        app: { id: 'app-1' },
        suggested_after_answer: { enable: false },
        opening_statement: '',
        opening_questions: [],
      },
    })
    await flushPromises()

    const state = (wrapper.vm.$ as any).setupState
    state.recorder = { stop: vi.fn(), getWAVBlob: () => new Blob(['voice']) }
    await state.handleStopRecord()

    expect(mocks.audioSuccess).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('aborts the active response and resets message state when the conversation route changes', async () => {
    const route = reactive(mocks.route); route.query = { conversation_id: 'conversation-before' }
    mocks.query.value = 'hello'
    let finishStream!: () => void
    let streamSignal: AbortSignal | undefined
    mocks.handleDebugChat.mockImplementationOnce((_appId, _query, _images, _conversationId, _callback, _deepThinking, signal) => { streamSignal = signal; return new Promise<void>((resolve) => { finishStream = resolve }) })
    const wrapper = shallowMount(PreviewDebugChat, {
      global: { stubs: { 'scroll-navigator': { template: '<div><slot /></div>' }, 'chat-composer': true } }, props: { app: { id: 'app-1' }, suggested_after_answer: { enable: false }, opening_statement: '', opening_questions: [] },
    })
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState; const pendingSubmit = state.handleSubmit()
    await flushPromises()
    state.message_id = 'old-message'; state.task_id = 'old-task'
    route.query = { ...route.query, conversation_id: 'conversation-after' }
    await flushPromises()

    expect(streamSignal?.aborted).toBe(true)
    expect(state.selectedConversationId).toBe('conversation-after')
    expect(state.message_id).toBe('')
    expect(state.task_id).toBe('')
    expect(mocks.loadDebugConversationMessages).toHaveBeenLastCalledWith('app-1', true, 'conversation-after')
    finishStream(); await pendingSubmit; wrapper.unmount()
  })
})
