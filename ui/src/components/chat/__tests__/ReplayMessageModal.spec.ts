import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import ReplayMessageModal from '../ReplayMessageModal.vue'

const mockExecuteReplay = vi.fn()
const mockClearReplay = vi.fn()
const mockLoading = ref(false)
const mockSnapshot = ref<any>(null)

vi.mock('@/hooks/use-conversation', () => ({
  useReplayMessage: () => ({
    loading: mockLoading,
    snapshot: mockSnapshot,
    executeReplay: mockExecuteReplay,
    clearReplay: mockClearReplay,
  }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

describe('ReplayMessageModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSnapshot.value = null
    mockLoading.value = false
  })

  it('opens with initial parameters and triggers replay with patch', async () => {
    const wrapper = mount(ReplayMessageModal, {
      global: {
        stubs: {
          'a-modal': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'a-textarea': {
            props: ['modelValue'],
            template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          },
          'a-tag': { template: '<span><slot /></span>' },
          'icon-check-circle': { template: '<span />' },
        },
      },
    })

    const vm = wrapper.vm as any
    vm.open('msg-123', 'initial question')
    await flushPromises()

    expect(wrapper.text()).toContain('initial question')

    const textarea = wrapper.find('textarea')
    await textarea.setValue('new patched prompt')

    mockExecuteReplay.mockResolvedValueOnce({
      message_id: 'msg-123',
      applied_patch_keys: ['preset_prompt'],
      input_snapshot: { query: 'initial question' },
    })

    await vm.handleReplay()

    expect(mockExecuteReplay).toHaveBeenCalledWith('msg-123', {
      patch: { preset_prompt: 'new patched prompt' },
    })
    expect(wrapper.emitted('replayed')).toBeTruthy()
  })

  it('displays applied patches when snapshot is present', async () => {
    const wrapper = mount(ReplayMessageModal, {
      global: {
        stubs: {
          'a-modal': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-textarea': true,
          'a-tag': { template: '<span class="tag-stub"><slot /></span>' },
          'icon-check-circle': { template: '<span />' },
        },
      },
    })

    mockSnapshot.value = {
      message_id: 'msg-123',
      applied_patch_keys: ['preset_prompt', 'model_config'],
      input_snapshot: { query: 'test snapshot query' },
    }
    await flushPromises()

    expect(wrapper.text()).toContain('chat.replayMessage.snapshotReady')
    expect(wrapper.text()).toContain('preset_prompt')
    expect(wrapper.text()).toContain('model_config')
    expect(wrapper.text()).toContain('test snapshot query')
  })
})
