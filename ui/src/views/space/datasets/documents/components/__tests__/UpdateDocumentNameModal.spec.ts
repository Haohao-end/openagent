import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import UpdateDocumentNameModal from '../UpdateDocumentNameModal.vue'

const mocks = vi.hoisted(() => ({ loadDocument: vi.fn(), saveName: vi.fn(), messageError: vi.fn() }))
vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return { useGetDocument: () => ({ document: ref({ name: '' }), loading: ref(false), loadDocument: mocks.loadDocument }), useUpdateDocumentName: () => ({ loading: ref(false), handleUpdateDocumentName: mocks.saveName }) }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.messageError, success: vi.fn() } }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

describe('UpdateDocumentNameModal', () => {
  it('does not close a reopened modal when an earlier save finishes', async () => {
    let resolveSave!: () => void
    mocks.saveName.mockReturnValueOnce(new Promise<void>((resolve) => { resolveSave = resolve }))
    const formStub = { methods: { resetFields: vi.fn() }, template: '<div><slot /></div>' }
    const wrapper = shallowMount(UpdateDocumentNameModal, { global: { stubs: { 'a-form': formStub } }, props: { visible: false, dataset_id: 'dataset', document_id: 'first' } })
    const state = (wrapper.vm.$ as any).setupState
    await wrapper.setProps({ visible: true }); await flushPromises()
    state.form.name = 'first'
    const pendingSave = state.handleSubmit({ errors: undefined })
    await flushPromises()
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true, document_id: 'second' }); await flushPromises()
    resolveSave()
    await pendingSave
    expect(wrapper.emitted('update:visible')).toBeUndefined()
  })
})

it('reports a document detail failure without saving a blank name', async () => {
  const unhandled: unknown[] = []
  mocks.loadDocument.mockReset().mockRejectedValueOnce(new Error('document details unavailable'))
  mocks.saveName.mockReset()
  mocks.messageError.mockReset()
  const wrapper = shallowMount(UpdateDocumentNameModal, {
    global: {
      config: { errorHandler: (error) => unhandled.push(error) },
      stubs: { 'a-form': { methods: { resetFields: vi.fn() }, template: '<div><slot /></div>' } },
    },
    props: { visible: false, dataset_id: 'dataset', document_id: 'document' },
  })

  await wrapper.setProps({ visible: true })
  await flushPromises()
  await (wrapper.vm.$ as any).setupState.handleSubmit({ errors: undefined })
  await flushPromises()

  expect(mocks.loadDocument).toHaveBeenCalledWith('dataset', 'document')
  expect(mocks.saveName).not.toHaveBeenCalled()
  expect(mocks.messageError).toHaveBeenCalledWith('document details unavailable')
  expect(unhandled).toHaveLength(0)
  wrapper.unmount()
})


it('ignores a detail load failure after the modal unmounts', async () => {
  let rejectLoad!: (error: Error) => void
  const unhandled: unknown[] = []
  mocks.loadDocument.mockReset().mockReturnValueOnce(new Promise((_, reject) => { rejectLoad = reject }))
  mocks.messageError.mockReset()
  const wrapper = shallowMount(UpdateDocumentNameModal, {
    global: {
      config: { errorHandler: (error) => unhandled.push(error) },
      stubs: { 'a-form': { methods: { resetFields: vi.fn() }, template: '<div><slot /></div>' } },
    },
    props: { visible: false, dataset_id: 'dataset', document_id: 'document' },
  })

  await wrapper.setProps({ visible: true })
  await flushPromises()
  wrapper.unmount()
  rejectLoad(new Error('document details unavailable'))
  await flushPromises()

  expect(mocks.messageError).not.toHaveBeenCalled()
  expect(unhandled).toHaveLength(0)
})
