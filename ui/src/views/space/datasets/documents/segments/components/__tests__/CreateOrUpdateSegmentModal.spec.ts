import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CreateOrUpdateSegmentModal from '../CreateOrUpdateSegmentModal.vue'

const mocks = vi.hoisted(() => ({ loadSegment: vi.fn(), updateSegment: vi.fn(), createSegment: vi.fn(), error: vi.fn() }))

vi.mock('@/hooks/use-dataset', () => ({
  useCreateSegment: () => ({ loading: false, handleCreateSegment: mocks.createSegment }),
  useGetSegment: () => ({ loadSegment: (...args: unknown[]) => mocks.loadSegment(...args) }),
  useUpdateSegment: () => ({ loading: false, handleUpdateSegment: mocks.updateSegment }),
}))

vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.error } }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

const formStub = { template: '<form><slot/></form>', methods: { resetFields: vi.fn() } }
const modalStub = { props: ['visible'], template: '<div v-if="visible"><slot/></div>' }
const textareaStub = { props: ['modelValue'], template: '<textarea :value="modelValue" />' }
const mountEditor = (segment_id = 'segment-1') => mount(CreateOrUpdateSegmentModal, {
  props: { dataset_id: 'dataset-1', document_id: 'document-1', segment_id, visible: true },
  global: { stubs: { 'a-modal': modalStub, 'a-form': formStub, 'a-textarea': textareaStub } },
})
const getSaveSegment = (wrapper: ReturnType<typeof mount>) =>
  (wrapper.vm.$ as unknown as { setupState: { saveSegment: (payload: { errors: undefined }) => Promise<void> } }).setupState.saveSegment

describe('CreateOrUpdateSegmentModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.loadSegment.mockResolvedValue({ content: 'existing segment', keywords: ['existing'] })
  })

  it.each(['create', 'update'] as const)('reports %s segment save failures', async (operation) => {
    const error = new Error('segment save failed')
    const submit = operation === 'create' ? mocks.createSegment : mocks.updateSegment
    submit.mockRejectedValueOnce(error)
    const wrapper = mountEditor(operation === 'update' ? 'segment-1' : '')
    const saveSegment = getSaveSegment(wrapper)
    let rejected = false
    try { await saveSegment({ errors: undefined }) } catch (_error) { rejected = true }

    expect(rejected).toBe(false)
    expect(mocks.error).toHaveBeenCalledWith('segment save failed')
    expect(wrapper.emitted('update:visible')).toBeUndefined()
    wrapper.unmount()
  })

  it('ignores failed saves after the modal closes or unmounts', async () => {
    let rejectClosed!: (error: Error) => void
    let rejectUnmounted!: (error: Error) => void
    const closedRequest = new Promise<void>((_, reject) => { rejectClosed = reject })
    const unmountedRequest = new Promise<void>((_, reject) => { rejectUnmounted = reject })
    mocks.updateSegment.mockReturnValueOnce(closedRequest).mockReturnValueOnce(unmountedRequest)
    const wrapper = mountEditor()
    const saveSegment = getSaveSegment(wrapper)
    const closedSave = saveSegment({ errors: undefined })
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    rejectClosed(new Error('closed save failed'))
    await closedSave
    wrapper.unmount()

    const unmountedWrapper = mountEditor()
    const unmountedSave = getSaveSegment(unmountedWrapper)({ errors: undefined })
    unmountedWrapper.unmount()
    rejectUnmounted(new Error('unmounted save failed'))
    await unmountedSave
    expect(mocks.error).not.toHaveBeenCalled()
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
