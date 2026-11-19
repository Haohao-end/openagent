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
    answer_length: 200,
  },
  target: {
    id: 'target-1',
    status: 'COMPLETED',
    error: '',
    latency: 1.5,
    total_token_count: 200,
    total_price: 0.08,
    answer_length: 260,
  },
  diff: {
    latency_diff: 0.3,
    total_token_count_diff: 50,
    message_token_count_diff: 10,
    answer_token_count_diff: 40,
    total_price_diff: 0.03,
    status_changed: false,
    error_changed: false,
    answer_match: false,
    answer_length_diff: 60,
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

describe('CompareMessagesModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockComparisonState.value = null
    mockLoading.value = false
  })

  it('renders diff rows when comparison data is available', async () => {
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
  })
})
