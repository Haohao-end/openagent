import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import UpdateDocumentNameModal from '../UpdateDocumentNameModal.vue'

const mocks = vi.hoisted(() => ({ loadDocument: vi.fn(), saveName: vi.fn() }))
vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return { useGetDocument: () => ({ document: ref({ name: '' }), loadDocument: mocks.loadDocument }), useUpdateDocumentName: () => ({ loading: ref(false), handleUpdateDocumentName: mocks.saveName }) }
})
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
