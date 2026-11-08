import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import DatasetRetrievalNodeInfo from '../DatasetRetrievalNodeInfo.vue'

const mocks = vi.hoisted(() => ({ load: vi.fn(), error: vi.fn() }))
vi.mock('@vue-flow/core', async () => {
  const { ref } = await import('vue')
  return { useVueFlow: () => ({ nodes: ref([]), edges: ref([]) }) }
})
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  return { useUpdateDraftAppConfig: () => ({ loading: ref(false), handleUpdateDraftAppConfig: vi.fn() }) }
})
vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return { useGetDatasetsWithPage: () => ({ loading: ref(false), paginator: ref({ current_page: 1, total_page: 0 }), datasets: ref([]), loadDatasets: mocks.load }) }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.error, warning: vi.fn() } }))

const node = {
  id: 'node-1',
  type: 'dataset-retrieval',
  data: { title: 'Dataset', description: '', inputs: [], meta: { datasets: [] }, retrieval_config: { retrieval_strategy: 'semantic', k: 4, score: 0 } },
}

it('reports dataset load failures and ignores a late scroll failure after unmount', async () => {
  let rejectLateLoad!: (error: Error) => void
  const lateLoad = new Promise<void>((_, reject) => { rejectLateLoad = reject })
  mocks.load.mockReset().mockRejectedValueOnce(new Error('network unavailable')).mockReturnValueOnce(lateLoad)
  mocks.error.mockReset()
  const wrapper = shallowMount(DatasetRetrievalNodeInfo, {
    props: { visible: true, node, loading: false },
  })
  await flushPromises()

  expect(mocks.error).toHaveBeenCalledWith('network unavailable')
  const state = (wrapper.vm.$ as any).setupState
  const scroll = state.handleScroll({ target: { scrollTop: 90, scrollHeight: 100, clientHeight: 20 } })
  wrapper.unmount()
  rejectLateLoad(new Error('late failure'))
  await scroll
  expect(mocks.error).toHaveBeenCalledTimes(1)
})
