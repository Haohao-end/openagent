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

it('reports recent-query failures on open and after a successful hit', async () => {
  const unhandled: unknown[] = []
  mocks.loadQueries.mockReset().mockRejectedValue(new Error('recent queries unavailable'))
  mocks.handleHit.mockReset().mockResolvedValue(true)
  mocks.messageError.mockReset()
  const wrapper = shallowMount(HitTestingModal, {
    global: { config: { errorHandler: (error) => unhandled.push(error) } },
    props: { visible: false, dataset_id: 'dataset-1' },
  })

  await wrapper.setProps({ visible: true })
  await flushPromises()
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
  const wrapper = shallowMount(HitTestingModal, {
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
  const wrapper = shallowMount(HitTestingModal, {
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
