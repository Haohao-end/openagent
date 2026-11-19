import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import MessageTraceModal from '../MessageTraceModal.vue'

const mockTrace = {
  message_id: 'msg-1',
  conversation_id: 'conv-1',
  app_id: 'app-1',
  status: 'SUCCEEDED',
  error: '',
  latency: 3.5,
  total_token_count: 420,
  total_price: 0.12,
  created_at: 1700000000,
  timeline: [
    {
      id: 'span-1',
      position: 0,
      event: 'thought',
      thought: 'Analyzing user request',
      observation: '',
      tool: '',
      tool_input: {},
      latency: 0.8,
      total_token_count: 120,
      total_price: 0.03,
      created_at: 1700000001,
    },
    {
      id: 'span-2',
      position: 1,
      event: 'tool',
      thought: 'Searching knowledge base',
      observation: 'Found 3 documents',
      tool: 'knowledge_retrieval',
      tool_input: { query: 'test query' },
      latency: 1.2,
      total_token_count: 200,
      total_price: 0.05,
      created_at: 1700000002,
    },
  ],
}

const mockLoadMessageTrace = vi.fn()
const mockClearMessageTrace = vi.fn()
const mockLoading = ref(false)
const mockTraceState = ref<any>(null)

vi.mock('@/hooks/use-conversation', () => ({
  useGetMessageTrace: () => ({
    loading: mockLoading,
    trace: mockTraceState,
    loadMessageTrace: mockLoadMessageTrace,
    clearMessageTrace: mockClearMessageTrace,
  }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

describe('MessageTraceModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockTraceState.value = null
    mockLoading.value = false
  })

  it('renders empty placeholder when trace is null', async () => {
    const wrapper = mount(MessageTraceModal, {
      global: {
        stubs: {
          'a-modal': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div class="empty-stub" />' },
          'a-tag': { template: '<span><slot /></span>' },
        },
      },
    })

    expect(wrapper.find('.empty-stub').exists()).toBe(true)
  })

  it('renders overview metrics and span timeline when trace is populated', async () => {
    const wrapper = mount(MessageTraceModal, {
      global: {
        stubs: {
          'a-modal': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div class="empty-stub" />' },
          'a-tag': { template: '<span><slot /></span>' },
        },
      },
    })

    mockTraceState.value = mockTrace
    await flushPromises()

    expect(wrapper.find('.empty-stub').exists()).toBe(false)
    expect(wrapper.text()).toContain('SUCCEEDED')
    expect(wrapper.text()).toContain('3.5s')
    expect(wrapper.text()).toContain('420')
    expect(wrapper.text()).toContain('¥0.12')
    expect(wrapper.text()).toContain('Analyzing user request')
    expect(wrapper.text()).toContain('knowledge_retrieval')
    expect(wrapper.text()).toContain('Found 3 documents')
    expect(wrapper.text()).toContain('#1')
    expect(wrapper.text()).toContain('#2')
  })

  it('renders fallback when timeline has no spans', async () => {
    const wrapper = mount(MessageTraceModal, {
      global: {
        stubs: {
          'a-modal': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div class="empty-stub" />' },
          'a-tag': { template: '<span><slot /></span>' },
        },
      },
    })

    mockTraceState.value = { ...mockTrace, timeline: [] }
    await flushPromises()

    expect(wrapper.text()).toContain('chat.messageTrace.noSpans')
  })
})
