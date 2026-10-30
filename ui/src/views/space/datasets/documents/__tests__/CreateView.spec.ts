import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { handleCreateDocuments, loadDocumentsStatus } = vi.hoisted(() => ({
  handleCreateDocuments: vi.fn().mockResolvedValue(undefined),
  loadDocumentsStatus: vi.fn().mockResolvedValue([{ id: 'doc-1', status: 'error' }]),
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
  beforeEach(() => {
    handleCreateDocuments.mockReset().mockResolvedValue(undefined)
    loadDocumentsStatus.mockReset().mockResolvedValue([{ id: 'doc-1', status: 'error' }])
  })

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

  it('does not submit document creation again when the first status lookup fails', async () => {
    loadDocumentsStatus.mockRejectedValueOnce(new Error('status unavailable'))
    const { default: CreateView } = await import('../CreateView.vue')
    const wrapper = mount(CreateView, {
      global: {
        config: { errorHandler: () => {} },
        stubs: { '*': true, 'a-button': ButtonStub, 'a-upload': UploadStub },
      },
    })
    const nextButton = () => wrapper.findAll('button').find((button) => button.text().includes('.next'))!

    await wrapper.get('[data-testid="upload"]').trigger('click')
    await nextButton().trigger('click')
    await flushPromises()
    await nextButton().trigger('click')
    await flushPromises()
    const retryButton = wrapper.findAll('button').find((button) => button.text().includes('.next'))
    if (retryButton) await retryButton.trigger('click')
    await flushPromises()

    expect(handleCreateDocuments).toHaveBeenCalledTimes(1)
    expect(loadDocumentsStatus).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('does not start polling when unmounted during the first status lookup', async () => {
    let resolveStatus!: (value: Array<{ id: string; status: string }>) => void
    loadDocumentsStatus.mockReturnValueOnce(new Promise((resolve) => { resolveStatus = resolve }))
    const intervalSpy = vi.spyOn(globalThis, 'setInterval')
      .mockReturnValue(1 as unknown as ReturnType<typeof setInterval>)
    const { default: CreateView } = await import('../CreateView.vue')
    const wrapper = mount(CreateView, {
      global: {
        stubs: { '*': true, 'a-button': ButtonStub, 'a-upload': UploadStub },
      },
    })
    const nextButton = () => wrapper.findAll('button').find((button) => button.text().includes('.next'))!

    try {
      await wrapper.get('[data-testid="upload"]').trigger('click')
      await nextButton().trigger('click')
      await flushPromises()
      await nextButton().trigger('click')
      await flushPromises()
      expect(loadDocumentsStatus).toHaveBeenCalledTimes(1)

      wrapper.unmount()
      resolveStatus([{ id: 'doc-1', status: 'processing' }])
      await flushPromises()

      expect((wrapper.vm as any).documents).toHaveLength(0)
      expect(intervalSpy).not.toHaveBeenCalled()
    } finally {
      wrapper.unmount()
      intervalSpy.mockRestore()
    }
  })

  it('does not surface a status failure after unmount', async () => {
    let rejectStatus!: (error: Error) => void
    loadDocumentsStatus.mockReturnValueOnce(new Promise((_, reject) => { rejectStatus = reject }))
    const errors: unknown[] = []
    const { default: CreateView } = await import('../CreateView.vue')
    const wrapper = mount(CreateView, {
      global: {
        config: { errorHandler: (error) => errors.push(error) },
        stubs: { '*': true, 'a-button': ButtonStub, 'a-upload': UploadStub },
      },
    })
    const nextButton = () => wrapper.findAll('button').find((button) => button.text().includes('.next'))!

    await wrapper.get('[data-testid="upload"]').trigger('click')
    await nextButton().trigger('click')
    await flushPromises()
    await nextButton().trigger('click')
    await flushPromises()
    wrapper.unmount()
    rejectStatus(new Error('late status failure'))
    await flushPromises()

    expect(errors).toEqual([])
  })
})
