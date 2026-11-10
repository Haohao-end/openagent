import { defineComponent, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import PreviewDebugHeader from '../PreviewDebugHeader.vue'

const mocks = vi.hoisted(() => ({ load: vi.fn(), save: vi.fn(), error: vi.fn(), summary: { value: '' } as { value: string } }))
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
vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.error } }))

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

it('reports a summary save failure and leaves the modal open', async () => {
  mocks.error.mockReset()
  mocks.load.mockReset().mockResolvedValue(undefined)
  mocks.save.mockReset().mockRejectedValueOnce(new Error(''))
  const wrapper = mount(PreviewDebugHeader, {
    props: { app_id: 'app-1', long_term_memory: { enable: true } },
    global: { stubs: { 'a-modal': ModalStub, 'a-button': ButtonStub, 'a-space': SpaceStub, 'a-textarea': true, 'icon-save': true, 'icon-close': true } },
  })
  const state = (wrapper.vm as any).$.setupState
  await state.openSummaryModal()

  await state.saveSummary().catch(() => undefined)

  expect(mocks.error).toHaveBeenCalledWith('appStudio.debug.summarySaveFailed')
  expect(state.summaryModalVisible).toBe(true)
  wrapper.unmount()
})

it('reports a summary load failure without opening the modal', async () => {
  mocks.error.mockReset()
  mocks.load.mockReset().mockRejectedValueOnce(new Error(''))
  const wrapper = mount(PreviewDebugHeader, {
    props: { app_id: 'app-1', long_term_memory: { enable: true } },
    global: { stubs: { 'a-modal': ModalStub, 'a-button': ButtonStub, 'a-space': SpaceStub, 'a-textarea': true, 'icon-save': true, 'icon-close': true } },
  })
  const state = (wrapper.vm as any).$.setupState

  await state.openSummaryModal().catch(() => undefined)

  expect(mocks.error).toHaveBeenCalledWith('appStudio.debug.summaryLoadFailed')
  expect(state.summaryModalVisible).toBe(false)
  wrapper.unmount()
})

it('does not report a summary load failure after changing apps', async () => {
  let reject!: (error: Error) => void
  mocks.error.mockReset()
  mocks.load.mockReset().mockReturnValueOnce(new Promise<void>((_resolve, rejectPromise) => { reject = rejectPromise }))
  const wrapper = mount(PreviewDebugHeader, {
    props: { app_id: 'app-1', long_term_memory: { enable: true } },
    global: { stubs: { 'a-modal': ModalStub, 'a-button': ButtonStub, 'a-space': SpaceStub, 'a-textarea': true, 'icon-save': true, 'icon-close': true } },
  })
  const state = (wrapper.vm as any).$.setupState
  const loading = state.openSummaryModal()
  await wrapper.setProps({ app_id: 'app-2' })
  reject(new Error('old app failed'))
  await loading

  expect(mocks.error).not.toHaveBeenCalled()
  expect(state.summaryModalVisible).toBe(false)
  wrapper.unmount()
})
