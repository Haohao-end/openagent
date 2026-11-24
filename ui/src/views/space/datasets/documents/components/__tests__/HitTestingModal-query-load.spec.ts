import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import HitTestingModal from '../HitTestingModal.vue'

const mocks = vi.hoisted(() => ({
  loadQueries: vi.fn(),
  clearQueries: vi.fn(),
  handleHit: vi.fn(),
  invalidateHits: vi.fn(),
  messageError: vi.fn(),
}))
vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return {
    useGetDatasetQueries: () => ({ loading: ref(false), queries: ref([]), loadDatasetQueries: mocks.loadQueries, clearDatasetQueries: mocks.clearQueries }),
    useHit: () => ({ loading: ref(false), hits: ref([{ id: 'hit-1', score: 0.9, content: 'hit', document: { name: 'Document' } }]), handleHit: mocks.handleHit, invalidateHitRequests: mocks.invalidateHits }),
  }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.messageError } }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

const defaultStubs = {
  'a-modal': { template: '<div><slot /></div>' },
  'a-button': { template: '<button><slot name="icon" /><slot /></button>' },
  'a-col': { template: '<div><slot /></div>' },
  'a-divider': { template: '<hr />' },
  'a-empty': { template: '<div><slot /></div>' },
  'a-form': { template: '<form><slot /></form>' },
  'a-form-item': { template: '<div><slot /></div>' },
  'a-input-number': { template: '<input type="number" />' },
  'a-progress': { template: '<div />' },
  'a-radio-group': { template: '<div><slot /></div>' },
  'a-row': { template: '<div><slot /></div>' },
  'a-slider': { template: '<div />' },
  'a-space': { template: '<div><slot /></div>' },
  'a-spin': { template: '<div><slot /></div>' },
  'a-table': { template: '<table><slot /></table>' },
  'a-table-column': { template: '<col />' },
  'a-tag': { template: '<span><slot /></span>' },
  'a-textarea': { template: '<textarea />' },
  'icon-close': { template: '<span class="icon-close" />' },
  'icon-file': { template: '<span class="icon-file" />' },
  'icon-language': { template: '<span class="icon-language" />' },
  'icon-pushpin': { template: '<span class="icon-pushpin" />' },
}

const mountHitTestingModal = (options: {
  props: { visible: boolean; dataset_id: string }
  global?: Record<string, any>
}) => {
  return shallowMount(HitTestingModal, {
    ...options,
    global: {
      ...options.global,
      stubs: {
        ...defaultStubs,
        ...options.global?.stubs,
      },
    },
  })
}

it('reports recent-query failures on open and after a successful hit', async () => {
  const unhandled: unknown[] = []
  mocks.loadQueries.mockReset().mockRejectedValue(new Error('recent queries unavailable'))
  mocks.handleHit.mockReset().mockResolvedValue(true)
  mocks.messageError.mockReset()
  const wrapper = mountHitTestingModal({
    global: { config: { errorHandler: (error: unknown) => unhandled.push(error) } },
    props: { visible: false, dataset_id: 'dataset-1' },
  })

  await wrapper.setProps({ visible: true })
  await flushPromises()
  expect(wrapper.exists()).toBe(true)
  const state = (wrapper.vm.$ as any).setupState
  state.hitTestingForm.query = 'test query'
  try {
    await state.handleHitTesting()
  } catch (error) {
    unhandled.push(error)
  }
  await flushPromises()

  expect(mocks.loadQueries).toHaveBeenCalledTimes(2)
  expect(mocks.messageError).toHaveBeenCalledTimes(2)
  expect(unhandled).toHaveLength(0)
  wrapper.unmount()
})

it('resets retrieval settings after the modal is reopened', async () => {
  mocks.loadQueries.mockReset().mockResolvedValue({ data: [] })
  const wrapper = mountHitTestingModal({
    props: { visible: false, dataset_id: 'dataset-1' },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  await wrapper.setProps({ visible: false })
  await flushPromises()
  await wrapper.setProps({ visible: true })
  await flushPromises()

  const state = (wrapper.vm.$ as any).setupState
  state.retrievalSettingForm.k = 8
  await wrapper.setProps({ visible: false })
  await flushPromises()
  await wrapper.setProps({ visible: true })
  await flushPromises()

  expect(state.hitTestingForm.k).toBe(5)
  expect(state.retrievalSettingForm.k).toBe(5)
  wrapper.unmount()
})

it('keeps cancelled settings edits separate from the active retrieval settings', async () => {
  const wrapper = mountHitTestingModal({
    props: { visible: true, dataset_id: 'dataset-1' },
  })
  const state = (wrapper.vm.$ as any).setupState
  state.retrievalSettingForm.k = 8
  state.hideRetrievalSettingModal()
  state.retrievalSettingForm.k = 9
  state.hideRetrievalSettingModal()

  expect(state.retrievalSettingForm.k).toBe(5)
  expect(state.hitTestingForm.k).toBe(5)
  wrapper.unmount()
})
