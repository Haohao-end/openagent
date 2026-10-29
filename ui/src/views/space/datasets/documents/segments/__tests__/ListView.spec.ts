import { defineComponent, nextTick, reactive, ref } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import SegmentListView from '../ListView.vue'

const mocks = vi.hoisted(() => ({
  route: { path: '/datasets/dataset/documents/doc/segments', params: { dataset_id: 'dataset', document_id: 'doc' }, query: { search_word: '' } },
  segment: { id: 'segment', position: 1, enabled: false, status: 'completed', content: 'example', character_count: 7, hit_count: 0 },
  updateEnabled: vi.fn(),
  loadDocument: vi.fn().mockResolvedValue(undefined),
  loadSegments: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return {
    useGetDocument: () => ({ document: ref({ name: 'Document', enabled: false, segment_count: 1, hit_count: 0, updated_at: 1 }), loadDocument: mocks.loadDocument }),
    useGetSegmentsWithPage: () => ({ loading: ref(false), segments: ref([mocks.segment]), paginator: ref({ current_page: 1, total_page: 1 }), loadSegments: mocks.loadSegments }),
    useDeleteSegment: () => ({ handleDelete: vi.fn() }),
    useUpdateSegmentEnabled: () => ({ handleUpdate: mocks.updateEnabled }),
  }
})

const switchStub = defineComponent({
  emits: ['update:modelValue', 'change'],
  template: '<button data-testid="segment-switch" @click="$emit(\'update:modelValue\', true); $emit(\'change\', true)" />',
})

const searchStub = defineComponent({
  props: { defaultValue: { type: String, default: '' } },
  setup(props) {
    const value = ref(props.defaultValue)
    return { value }
  },
  template: '<input data-testid="segment-search" :value="value" />',
})

const mountView = () => shallowMount(SegmentListView, { global: { stubs: { 'a-switch': switchStub, 'a-input-search': searchStub } } })

beforeEach(() => {
  mocks.route = reactive({
    path: '/datasets/dataset/documents/doc/segments',
    params: { dataset_id: 'dataset', document_id: 'doc' },
    query: { search_word: '' },
  })
  mocks.segment.enabled = false
  mocks.updateEnabled.mockReset().mockRejectedValue(new Error('offline'))
  mocks.loadDocument.mockClear()
  mocks.loadSegments.mockClear()
})

it('syncs the search input when the route query changes', async () => {
  mocks.route.query.search_word = 'alpha'
  const wrapper = mountView()
  const searchValue = () => (wrapper.get('[data-testid="segment-search"]').element as HTMLInputElement).value

  expect(searchValue()).toBe('alpha')
  mocks.route.query.search_word = 'beta'
  await nextTick()
  expect(searchValue()).toBe('beta')
  mocks.route.query.search_word = ''
  await nextTick()
  expect(searchValue()).toBe('')
  wrapper.unmount()
})

it('keeps the persisted segment status when the update fails', async () => {
  const wrapper = mountView()

  await wrapper.get('[data-testid="segment-switch"]').trigger('click')
  await flushPromises()

  expect(mocks.updateEnabled).toHaveBeenCalledWith('dataset', 'doc', 'segment', true)
  expect(mocks.segment.enabled).toBe(false)
  expect(wrapper.text()).toContain('space.datasets.documents.statuses.disabled')

  mocks.updateEnabled.mockResolvedValue(undefined)
  await wrapper.get('[data-testid="segment-switch"]').trigger('click')
  await flushPromises()
  expect(mocks.segment.enabled).toBe(true)
  expect(wrapper.text()).toContain('space.datasets.documents.statuses.enabled')
})

it('reloads the document and segments when reused for another document', async () => {
  const wrapper = mountView()
  mocks.loadDocument.mockClear()
  mocks.loadSegments.mockClear()

  mocks.route.params.dataset_id = 'dataset-b'
  mocks.route.params.document_id = 'document-b'
  await nextTick()
  await flushPromises()

  expect(mocks.loadDocument).toHaveBeenCalledWith('dataset-b', 'document-b')
  expect(mocks.loadSegments).toHaveBeenCalledWith('dataset-b', 'document-b', true, '')
  wrapper.unmount()
})
