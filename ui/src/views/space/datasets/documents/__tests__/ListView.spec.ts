import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ loadDocuments: vi.fn(), loadDataset: vi.fn(), route: { params: { dataset_id: 'dataset-1' }, query: { current_page: 'invalid', page_size: '0' } } }))

vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return {
    useDeleteDocument: () => ({ handleDelete: vi.fn() }),
    useGetDataset: () => ({ dataset: ref({}), loadDataset: mocks.loadDataset }),
    useGetDocumentsWithPage: () => ({ documents: ref([]), loading: ref(false), loadDocuments: mocks.loadDocuments, paginator: { current_page: 1, page_size: 20, total_record: 0 } }),
    useUpdateDocumentEnabled: () => ({ handleUpdate: vi.fn() }),
  }
})
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@arco-design/web-vue', () => ({ Message: { info: vi.fn(), success: vi.fn(), warning: vi.fn(), error: vi.fn() } }))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ push: vi.fn() }) }))

describe('dataset document pagination query', () => {
  beforeEach(() => {
    mocks.loadDocuments.mockResolvedValue(undefined)
    mocks.loadDataset.mockResolvedValue(undefined)
  })

  it('uses valid defaults when the URL pagination values are invalid', async () => {
    const { default: ListView } = await import('../ListView.vue')
    mount(ListView, { global: { stubs: { '*': true, HitTestingModal: true, UpdateDocumentNameModal: true } } })
    await flushPromises()
    expect(mocks.loadDocuments).toHaveBeenCalledWith('dataset-1', { current_page: 1, page_size: 20, search_word: '' })
  })

  it('does not report document load errors after component unmounts', async () => {
    let rejectDocs!: (err: Error) => void
    mocks.loadDocuments.mockReturnValueOnce(new Promise((_, reject) => { rejectDocs = reject }))
    const { Message } = await import('@arco-design/web-vue')
    const { default: ListView } = await import('../ListView.vue')
    const wrapper = mount(ListView, { global: { stubs: { '*': true, HitTestingModal: true, UpdateDocumentNameModal: true } } })
    await flushPromises()
    wrapper.unmount()
    rejectDocs(new Error('late document load failure'))
    await flushPromises()
    expect(Message.error).not.toHaveBeenCalledWith('late document load failure')
  })
})
