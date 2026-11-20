import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import FeedbackModal from '../FeedbackModal.vue'

const mockSubmitFeedback = vi.fn()
const mockClearFeedback = vi.fn()
const mockLoading = ref(false)
const mockSubmittedFeedbackId = ref<string | null>(null)

vi.mock('@/hooks/use-feedback', () => ({
  useFeedback: () => ({
    loading: mockLoading,
    submittedFeedbackId: mockSubmittedFeedbackId,
    submitFeedback: mockSubmitFeedback,
    clearFeedback: mockClearFeedback,
  }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

describe('FeedbackModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSubmittedFeedbackId.value = null
    mockLoading.value = false
  })

  it('opens and submits like feedback', async () => {
    const wrapper = mount(FeedbackModal, {
      global: {
        stubs: {
          'a-modal': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'a-textarea': {
            props: ['modelValue'],
            template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          },
          'icon-thumb-up': { template: '<span />' },
          'icon-thumb-down': { template: '<span />' },
        },
      },
    })

    const vm = wrapper.vm as any
    vm.open('app-test', 'msg-test', 1)
    await flushPromises()

    const textarea = wrapper.find('textarea')
    await textarea.setValue('Helpful answer!')

    mockSubmitFeedback.mockResolvedValueOnce({ id: 'fb-created-1' })

    await vm.handleSubmit()

    expect(mockSubmitFeedback).toHaveBeenCalledWith('app-test', {
      target_id: 'msg-test',
      target_type: 'message',
      rating: 1,
      content: 'Helpful answer!',
    })
    expect(wrapper.emitted('submitted')?.[0]).toEqual(['fb-created-1'])
  })

  it('warns when rating is not selected', async () => {
    const { Message } = await import('@arco-design/web-vue')
    const wrapper = mount(FeedbackModal, {
      global: {
        stubs: {
          'a-modal': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-button': true,
          'a-textarea': true,
          'icon-thumb-up': true,
          'icon-thumb-down': true,
        },
      },
    })

    const vm = wrapper.vm as any
    vm.open('app-test', 'msg-test')
    await flushPromises()

    await vm.handleSubmit()

    expect(mockSubmitFeedback).not.toHaveBeenCalled()
    expect(Message.warning).toHaveBeenCalledWith('chat.feedback.selectRating')
  })

  it('does not dispatch submitFeedback when loading is already true', async () => {
    const wrapper = mount(FeedbackModal, {
      global: {
        stubs: {
          'a-modal': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-button': true,
          'a-textarea': true,
          'icon-thumb-up': true,
          'icon-thumb-down': true,
        },
      },
    })

    const vm = wrapper.vm as any
    vm.open('app-test', 'msg-test', 1)
    await flushPromises()

    mockLoading.value = true
    await vm.handleSubmit()

    expect(mockSubmitFeedback).not.toHaveBeenCalled()
  })
})
