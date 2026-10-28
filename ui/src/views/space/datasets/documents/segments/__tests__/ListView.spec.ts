import { defineComponent } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import SegmentListView from '../ListView.vue'

const mocks = vi.hoisted(() => ({
  route: { path: '/datasets/dataset/documents/doc/segments', params: { dataset_id: 'dataset', document_id: 'doc' }, query: {} },
  segment: { id: 'segment', position: 1, enabled: false, status: 'completed', content: 'example', character_count: 7, hit_count: 0 },
  updateEnabled: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return {
    useGetDocument: () => ({ document: ref({ name: 'Document', enabled: false, segment_count: 1, hit_count: 0, updated_at: 1 }), loadDocument: vi.fn() }),
    useGetSegmentsWithPage: () => ({ loading: ref(false), segments: ref([mocks.segment]), paginator: ref({ current_page: 1, total_page: 1 }), loadSegments: vi.fn() }),
    useDeleteSegment: () => ({ handleDelete: vi.fn() }),
    useUpdateSegmentEnabled: () => ({ handleUpdate: mocks.updateEnabled }),
  }
})

const switchStub = defineComponent({
  emits: ['update:modelValue', 'change'],
  template: '<button data-testid="segment-switch" @click="$emit(\'update:modelValue\', true); $emit(\'change\', true)" />',
})

const mountView = () => shallowMount(SegmentListView, { global: { stubs: { 'a-switch': switchStub } } })

beforeEach(() => {
  mocks.segment.enabled = false
  mocks.updateEnabled.mockReset().mockRejectedValue(new Error('offline'))
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
