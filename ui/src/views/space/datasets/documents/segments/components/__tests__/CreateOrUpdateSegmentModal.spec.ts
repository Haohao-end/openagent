import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CreateOrUpdateSegmentModal from '../CreateOrUpdateSegmentModal.vue'

const mocks = vi.hoisted(() => ({ loadSegment: vi.fn() }))

vi.mock('@/hooks/use-dataset', () => ({
  useCreateSegment: () => ({ loading: false, handleCreateSegment: vi.fn() }),
  useGetSegment: () => ({ loadSegment: (...args: unknown[]) => mocks.loadSegment(...args) }),
  useUpdateSegment: () => ({ loading: false, handleUpdateSegment: vi.fn() }),
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
})
