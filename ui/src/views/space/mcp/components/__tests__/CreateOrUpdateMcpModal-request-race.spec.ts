import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ getMcpCategories: vi.fn(), getMcpProvider: vi.fn(), generateMcpIconPreview: vi.fn(), regenerateMcpIcon: vi.fn(), uploadImage: vi.fn(), uploadImageUrl: null as any, mcpSchemaAssistantChat: vi.fn(), messageError: vi.fn(), messageSuccess: vi.fn() }))
vi.mock('@/services/mcp', () => ({
  createMcpProvider: vi.fn(), updateMcpProvider: vi.fn(),
  generateMcpIconPreview: mocks.generateMcpIconPreview, regenerateMcpIcon: mocks.regenerateMcpIcon,
  getMcpCategories: mocks.getMcpCategories, getMcpProvider: mocks.getMcpProvider,
}))
vi.mock('@/services/ai', () => ({ mcpSchemaAssistantChat: mocks.mcpSchemaAssistantChat }))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.messageError, success: mocks.messageSuccess, warning: vi.fn() } }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key, locale: { value: 'en-US' } }) }))
vi.mock('@/hooks/use-upload-file', async () => {
  const { ref } = await import('vue')
  return { useUploadImage: () => {
    const image_url = ref('')
    mocks.uploadImageUrl = image_url
    return { image_url, handleUploadImage: mocks.uploadImage }
  } }
})
import CreateOrUpdateMcpModal from '../CreateOrUpdateMcpModal.vue'
const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (error: Error) => void
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}
const provider = (name: string) => ({ data: { name, description: name, icon: '' } })
const IconStub = { props: ['name', 'icon', 'onGenerate', 'onUpload', 'loading'], template: '<span />' }
const SlotStub = { template: '<div><slot /></div>' }
const ModalStub = { props: ['visible'], template: '<div v-if="visible"><slot /></div>' }
const SpinStub = { props: ['loading'], template: '<div><slot /></div>' }
const FormStub = { template: '<form><slot /></form>', methods: { resetFields() {} } }
const OptionStub = { props: ['value'], template: '<div :data-value="value"><slot /></div>' }
const stubs = {
  'a-modal': ModalStub, 'a-spin': SpinStub, 'a-form': FormStub, 'a-form-item': SlotStub,
  'a-button': SlotStub, 'a-textarea': SlotStub, 'a-select': SlotStub,
  'a-input-number': SlotStub, 'a-input': SlotStub, 'a-option': OptionStub, IconUploadGenerator: IconStub,
}
const mountModal = () => mount(CreateOrUpdateMcpModal, {
  props: { visible: false, mcp_provider_id: '' }, global: { stubs },
})
describe('MCP provider request ordering', () => {
  it('ignores stale results after reopen and provider changes', async () => {
    mocks.getMcpCategories.mockResolvedValue({ data: { categories: [] } })
    const a = deferred<ReturnType<typeof provider>>()
    const b = deferred<ReturnType<typeof provider>>()
    const c = deferred<ReturnType<typeof provider>>()
    mocks.getMcpProvider.mockImplementation((id: string) => ({ A: a, B: b, C: c } as Record<string, typeof a>)[id].promise)
    const wrapper = mountModal()
    await wrapper.setProps({ visible: true, mcp_provider_id: 'A' }); await flushPromises()
    await wrapper.setProps({ visible: false, mcp_provider_id: '' })
    await wrapper.setProps({ visible: true, mcp_provider_id: 'B' }); await flushPromises()
    a.resolve(provider('A')); await flushPromises()
    expect(wrapper.findComponent(IconStub).props('name')).toBe('')
    await wrapper.setProps({ mcp_provider_id: 'C' }); await flushPromises()
    expect(mocks.getMcpProvider.mock.calls.map(([id]) => id)).toEqual(['A', 'B', 'C'])
    b.reject(new Error('stale B failure')); await flushPromises()
    expect(mocks.messageError).not.toHaveBeenCalled()
    expect(wrapper.findComponent(SpinStub).props('loading')).toBe(true)
    c.resolve(provider('C')); await flushPromises()
    expect(wrapper.findComponent(IconStub).props('name')).toBe('C')
    expect(wrapper.findComponent(SpinStub).props('loading')).toBe(false)
    wrapper.unmount()
  })

  it('keeps the latest categories when an older request fails last', async () => {
    const older = deferred<{ data: { categories: { id: string; name: string }[] } }>()
    const newer = deferred<{ data: { categories: { id: string; name: string }[] } }>()
    mocks.getMcpCategories.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    mocks.getMcpProvider.mockResolvedValue(provider('B'))
    const wrapper = mountModal()
    await wrapper.setProps({ visible: true, mcp_provider_id: 'A' }); await flushPromises()
    await wrapper.setProps({ mcp_provider_id: 'B' }); await flushPromises()
    newer.resolve({ data: { categories: [{ id: 'current', name: 'Current' }] } }); await flushPromises()
    older.reject(new Error('stale categories failure')); await flushPromises()

    expect(wrapper.find('[data-value="current"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('ignores schema generation from a closed modal session', async () => {
    mocks.getMcpCategories.mockResolvedValue({ data: { categories: [] } })
    mocks.getMcpProvider.mockResolvedValue(provider('B'))
    const generation = deferred<void>()
    let emitChunk: ((event: any) => void) | undefined
    mocks.mcpSchemaAssistantChat.mockImplementation((_question, onEvent) => {
      emitChunk = onEvent
      return generation.promise
    })
    const wrapper = mountModal()
    await wrapper.setProps({ visible: true, mcp_provider_id: 'A' })
    await flushPromises()

    const state = (wrapper.vm.$ as any).setupState
    state.aiQuestion = 'describe provider A'
    const pending = state.handleGenerateByAI()
    await flushPromises()
    await wrapper.setProps({ visible: false, mcp_provider_id: '' })
    await flushPromises()
    await wrapper.setProps({ visible: true, mcp_provider_id: 'B' })
    await flushPromises()

    emitChunk!({ data: { content: '{"name":"provider A schema"}' } })
    generation.resolve()
    await pending

    expect(state.form.name).toBe('B')
    wrapper.unmount()
  })

  it('ignores icon results from a previous provider modal session', async () => {
    mocks.getMcpCategories.mockResolvedValue({ data: { categories: [] } })
    mocks.getMcpProvider.mockImplementation(async (id: string) => ({
      data: { ...provider(id).data, icon: `icon-${id}` },
    }))
    const generationA = deferred<{ data: { icon: string } }>()
    const generationB = deferred<{ data: { icon: string } }>()
    mocks.regenerateMcpIcon.mockImplementation((id: string) => id === 'A' ? generationA.promise : generationB.promise)
    const uploadA = deferred<void>()
    mocks.uploadImage.mockImplementation(async () => {
      await uploadA.promise
      mocks.uploadImageUrl.value = 'icon-A-uploaded'
    })

    const wrapper = mountModal()
    await wrapper.setProps({ visible: true, mcp_provider_id: 'A' })
    await flushPromises()
    const oldIcon = wrapper.findComponent(IconStub)
    const oldGeneration = (oldIcon.props('onGenerate') as () => Promise<void>)()
    const oldUpload = (oldIcon.props('onUpload') as (file: File) => Promise<void>)(new File(['icon'], 'mcp-icon.png'))
    expect(mocks.regenerateMcpIcon).toHaveBeenCalledWith('A')

    await wrapper.setProps({ visible: false, mcp_provider_id: '' })
    await wrapper.setProps({ visible: true, mcp_provider_id: 'B' })
    await flushPromises()
    expect(wrapper.findComponent(IconStub).props('icon')).toBe('icon-B')
    const currentIcon = wrapper.findComponent(IconStub)
    const currentGeneration = (currentIcon.props('onGenerate') as () => Promise<void>)()
    await flushPromises()
    expect(currentIcon.props('loading')).toBe(true)

    generationA.resolve({ data: { icon: 'icon-A-generated' } })
    await oldGeneration
    expect(wrapper.findComponent(IconStub).props('icon')).toBe('icon-B')
    expect(wrapper.findComponent(IconStub).props('loading')).toBe(true)

    uploadA.resolve()
    await oldUpload
    expect(wrapper.findComponent(IconStub).props('icon')).toBe('icon-B')
    generationB.resolve({ data: { icon: 'icon-B-generated' } })
    await currentGeneration
    expect(wrapper.findComponent(IconStub).props('icon')).toBe('icon-B-generated')
    expect(wrapper.findComponent(IconStub).props('loading')).toBe(false)
    expect(mocks.messageSuccess).toHaveBeenCalledWith('space.mcp.iconGenerateSuccess')
    wrapper.unmount()
  })
})
