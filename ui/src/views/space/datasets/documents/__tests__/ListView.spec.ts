import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ loadDocuments: vi.fn().mockResolvedValue(undefined), route: { params: { dataset_id: 'dataset-1' }, query: { current_page: 'invalid', page_size: '0' } } }))

vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return {
    useDeleteDocument: () => ({ handleDelete: vi.fn() }),
    useGetDataset: () => ({ dataset: ref({}), loadDataset: vi.fn() }),
    useGetDocumentsWithPage: () => ({ documents: ref([]), loading: ref(false), loadDocuments: mocks.loadDocuments, paginator: { current_page: 1, page_size: 20, total_record: 0 } }),
    useUpdateDocumentEnabled: () => ({ handleUpdate: vi.fn() }),
  }
})
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ push: vi.fn() }) }))

describe('dataset document pagination query', () => {
  beforeEach(() => mocks.loadDocuments.mockClear())

  it('uses valid defaults when the URL pagination values are invalid', async () => {
    const { default: ListView } = await import('../ListView.vue')
    mount(ListView, { global: { stubs: { '*': true, HitTestingModal: true, UpdateDocumentNameModal: true } } })
    await flushPromises()
    expect(mocks.loadDocuments).toHaveBeenCalledWith('dataset-1', { current_page: 1, page_size: 20, search_word: '' })
  })
})
