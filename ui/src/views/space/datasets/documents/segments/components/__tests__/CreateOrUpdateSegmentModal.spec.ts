import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CreateOrUpdateSegmentModal from '../CreateOrUpdateSegmentModal.vue'

const mocks = vi.hoisted(() => ({ loadSegment: vi.fn(), updateSegment: vi.fn() }))

vi.mock('@/hooks/use-dataset', () => ({
  useCreateSegment: () => ({ loading: false, handleCreateSegment: vi.fn() }),
  useGetSegment: () => ({ loadSegment: (...args: unknown[]) => mocks.loadSegment(...args) }),
  useUpdateSegment: () => ({ loading: false, handleUpdateSegment: mocks.updateSegment }),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

const formStub = { template: '<form><slot/></form>', methods: { resetFields: vi.fn() } }
const modalStub = { props: ['visible'], template: '<div v-if="visible"><slot/></div>' }
const textareaStub = { props: ['modelValue'], template: '<textarea :value="modelValue" />' }

describe('CreateOrUpdateSegmentModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.loadSegment.mockResolvedValue({ content: 'existing segment', keywords: ['existing'] })
  })

  it('clears edited values before opening a new segment form', async () => {
    const wrapper = mount(CreateOrUpdateSegmentModal, {
      props: { dataset_id: 'dataset-1', document_id: 'document-1', segment_id: '', visible: false },
      global: { stubs: { 'a-modal': modalStub, 'a-form': formStub, 'a-textarea': textareaStub } },
    })

    await wrapper.setProps({ segment_id: 'segment-1', visible: true })
    await flushPromises()
    expect(wrapper.get('textarea').element.value).toBe('existing segment')

    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ segment_id: '', visible: true })
    await flushPromises()

    expect(wrapper.get('textarea').element.value).toBe('')
  })

  it('keeps a reopened segment editor open after an earlier save completes', async () => {
    let resolve!: () => void
    mocks.updateSegment.mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
    const wrapper = mount(CreateOrUpdateSegmentModal, {
      props: { dataset_id: 'dataset-1', document_id: 'document-1', segment_id: 'segment-1', visible: true },
      global: { stubs: { 'a-modal': modalStub, 'a-form': formStub, 'a-textarea': textareaStub } },
    })
    const { saveSegment } = (wrapper.vm.$ as unknown as {
      setupState: { saveSegment: (payload: { errors: undefined }) => Promise<void> }
    }).setupState
    const save = saveSegment({ errors: undefined })
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true, segment_id: 'segment-2' })
    resolve()
    await save
    expect(wrapper.emitted('update:visible')).toBeUndefined()
    wrapper.unmount()
  })
})
