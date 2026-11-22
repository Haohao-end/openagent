import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import CompareMessagesModal from '../CompareMessagesModal.vue'

const mockComparison = {
  base: {
    id: 'base-1',
    status: 'COMPLETED',
    error: '',
    latency: 1.2,
    total_token_count: 150,
    total_price: 0.05,
    answer: 'Base answer text',
    answer_length: 16,
  },
  target: {
    id: 'target-1',
    status: 'COMPLETED',
    error: 'Model timeout',
    latency: 1.5,
    total_token_count: 200,
    total_price: 0.08,
    answer: 'Target answer text differing',
    answer_length: 28,
  },
  diff: {
    latency_diff: 0.3,
    total_token_count_diff: 50,
    message_token_count_diff: 10,
    answer_token_count_diff: 40,
    total_price_diff: 0.03,
    status_changed: false,
    error_changed: true,
    answer_match: false,
    answer_length_diff: 12,
  },
}

const mockLoadComparison = vi.fn()
const mockClearComparison = vi.fn()
const mockLoading = ref(false)
const mockComparisonState = ref<any>(null)

vi.mock('@/hooks/use-conversation', () => ({
  useCompareMessages: () => ({
    loading: mockLoading,
    comparison: mockComparisonState,
    loadComparison: mockLoadComparison,
    clearComparison: mockClearComparison,
  }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    info: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

describe('CompareMessagesModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockComparisonState.value = null
    mockLoading.value = false
  })

  it('renders diff rows and side-by-side answers when comparison data is available', async () => {
    const wrapper = mount(CompareMessagesModal, {
      global: {
        stubs: {
          'a-modal': {
            template: '<div><slot /></div>',
          },
          'a-spin': {
            template: '<div><slot /></div>',
          },
          'a-empty': {
            template: '<div class="empty-stub" />',
          },
        },
      },
    })

    expect(wrapper.find('.empty-stub').exists()).toBe(true)

    mockComparisonState.value = mockComparison
    await flushPromises()

    expect(wrapper.find('.empty-stub').exists()).toBe(false)
    expect(wrapper.text()).toContain('chat.compareMessages.latency')
    expect(wrapper.text()).toContain('1.2s')
    expect(wrapper.text()).toContain('1.5s')
    expect(wrapper.text()).toContain('+0.3s')
    expect(wrapper.text()).toContain('chat.compareMessages.tokens')
    expect(wrapper.text()).toContain('+50')
    expect(wrapper.text()).toContain('chat.compareMessages.error')
    expect(wrapper.text()).toContain('Model timeout')
    expect(wrapper.text()).toContain('chat.compareMessages.changed')
    expect(wrapper.text()).toContain('chat.compareMessages.answerComparison')
    expect(wrapper.text()).toContain('Base answer text')
    expect(wrapper.text()).toContain('Target answer text differing')
    expect(wrapper.text()).toContain('chat.compareMessages.answerMismatch')
  })

  it('invokes loadComparison with target first and base second', async () => {
    const wrapper = mount(CompareMessagesModal, {
      global: {
        stubs: {
          'a-modal': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div class="empty-stub" />' },
        },
      },
    })

    wrapper.vm.open('base-msg-123')
    await wrapper.vm.handleCompare('target-msg-456')

    expect(mockLoadComparison).toHaveBeenCalledWith('target-msg-456', 'base-msg-123')
  })

  it('shows an error message instead of throwing when the comparison request fails', async () => {
    const { Message } = await import('@arco-design/web-vue')
    const loadError = new Error('compare request failed')
    mockLoadComparison.mockRejectedValueOnce(loadError)

    const wrapper = mount(CompareMessagesModal, {
      global: {
        stubs: {
          'a-modal': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div class="empty-stub" />' },
        },
      },
    })

    wrapper.vm.open('base-msg-123')
    await expect(wrapper.vm.handleCompare('target-msg-456')).resolves.toBeUndefined()
    await flushPromises()

    expect(Message.error).toHaveBeenCalledWith('compare request failed')
  })
})
