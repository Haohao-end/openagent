import { defineComponent, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import PreviewDebugHeader from '../PreviewDebugHeader.vue'

const mocks = vi.hoisted(() => ({ load: vi.fn(), save: vi.fn(), summary: { value: '' } as { value: string } }))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  const summary = ref('summary')
  mocks.summary = summary
  return {
    useGetDebugConversationSummary: () => ({ debug_conversation_summary: summary, loadDebugConversationSummary: mocks.load }),
    useUpdateDebugConversationSummary: () => ({ loading: ref(false), handleUpdateDebugConversationSummary: mocks.save }),
  }
})
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible"><slot /></div>' })
const ButtonStub = defineComponent({ emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' })
const SpaceStub = defineComponent({ template: '<div><slot /></div>' })

it('does not open the new app modal when an old summary load finishes late', async () => {
  let resolve!: () => void
  mocks.summary.value = ''
  mocks.load.mockReset().mockImplementationOnce((_appId, isCurrent = () => true) => new Promise<void>((done) => {
    resolve = () => {
      if (isCurrent()) mocks.summary.value = 'old app summary'
      done()
    }
  }))
  const wrapper = mount(PreviewDebugHeader, {
    props: { app_id: 'app-1', long_term_memory: { enable: true } },
    global: { stubs: { 'a-modal': ModalStub, 'a-button': ButtonStub, 'a-space': SpaceStub, 'a-textarea': true, 'icon-save': true, 'icon-close': true } },
  })
  const state = (wrapper.vm as any).$.setupState
  const loadingOldSummary = state.openSummaryModal()

  await wrapper.setProps({ app_id: 'app-2' })
  resolve()
  await loadingOldSummary

  expect(state.summaryModalVisible).toBe(false)
  expect(state.debug_conversation_summary).toBe('')
  wrapper.unmount()
})

it.each(['reopen', 'unmount'] as const)('ignores an old summary save after the modal %s', async (action) => {
  let resolve!: () => void
  mocks.summary.value = 'summary'
  mocks.load.mockReset().mockResolvedValue(undefined)
  mocks.save.mockReset().mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
  const wrapper = mount(PreviewDebugHeader, {
    props: { app_id: 'app-1', long_term_memory: { enable: true } },
    global: { stubs: { 'a-modal': ModalStub, 'a-button': ButtonStub, 'a-space': SpaceStub, 'a-textarea': true, 'icon-save': true, 'icon-close': true } },
  })
  const state = (wrapper.vm as any).$.setupState
  await state.openSummaryModal()
  await nextTick()
  const saveButton = wrapper.findAll('button').find((button) => button.text().includes('common.actions.save'))!
  const saving = saveButton.trigger('click')
  await nextTick()
  if (action === 'reopen') {
    state.summaryModalVisible = false
    await nextTick()
    await state.openSummaryModal()
  } else {
    wrapper.unmount()
  }

  resolve()
  await flushPromises()
  expect(state.summaryModalVisible).toBe(true)
  expect(mocks.save).toHaveBeenCalledWith('app-1', 'summary')
  await saving
  if (action === 'reopen') wrapper.unmount()
})
