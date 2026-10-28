import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

const { handleCreateDocuments, loadDocumentsStatus } = vi.hoisted(() => ({
  handleCreateDocuments: vi.fn().mockResolvedValue(undefined),
  loadDocumentsStatus: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return {
    useCreateDocuments: () => ({ loading: ref(false), create_documents_result: ref({ batch: 'batch-1' }), handleCreateDocuments }),
    useGetDocumentsStatus: () => ({
      documents_status_result: ref([{ id: 'doc-1', name: 'broken.pdf', size: 1024, segment_count: 0, completed_segment_count: 0, status: 'error' }]),
      loadDocumentsStatus,
    }),
  }
})
vi.mock('@/hooks/use-upload-file', async () => {
  const { ref } = await import('vue')
  return { useUploadFile: () => ({ upload_file: ref({}), handleUploadFile: vi.fn() }) }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { error: vi.fn(), warning: vi.fn() } }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRoute: () => ({ params: { dataset_id: 'dataset-1' } }),
}))

const ButtonStub = defineComponent({
  emits: ['click'],
  setup(_props, { emit, slots }) {
    return () => h('button', { onClick: () => emit('click') }, slots.default?.())
  },
})
const UploadStub = defineComponent({
  emits: ['update:fileList'],
  setup(_props, { emit }) {
    return () => h('button', { 'data-testid': 'upload', onClick: () => emit('update:fileList', [{ response: { id: 'file-1' } }]) })
  },
})

describe('document creation status', () => {
  it('shows parsing errors when the document has no segments', async () => {
    const { default: CreateView } = await import('../CreateView.vue')
    const wrapper = mount(CreateView, { global: { stubs: { '*': true, 'a-button': ButtonStub, 'a-upload': UploadStub } } })
    const nextButton = () => wrapper.findAll('button').find((button) => button.text().includes('.next'))!

    await wrapper.get('[data-testid="upload"]').trigger('click')
    await nextButton().trigger('click')
    await flushPromises()
    await nextButton().trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('space.datasets.documents.create.processingError')
    wrapper.unmount()
  })
})
