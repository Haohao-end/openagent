import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick, reactive } from 'vue'
import ToolListView from '../ListView.vue'

const mocks = vi.hoisted(() => ({ route: null as any, imageUrl: null as any, upload: vi.fn(), providers: [] as any[], loadProvider: vi.fn(), loadProviders: vi.fn(), openapiSchemaAssistantChat: vi.fn(), validateOpenapi: vi.fn(), success: vi.fn(), error: vi.fn(), generatePreview: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ replace: (target: any) => Object.assign(mocks.route, target) }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/stores/account', () => ({ useAccountStore: () => ({ account: { avatar: '', name: 'Owner' } }) }))
vi.mock('@/utils/helper', () => ({ getUserAvatarUrl: () => '' }))
vi.mock('@/services/ai', () => ({ openapiSchemaAssistantChat: mocks.openapiSchemaAssistantChat }))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: mocks.success, error: mocks.error, warning: vi.fn() } }))
vi.mock('@/components/IconUploadGenerator.vue', async () => {
  const { defineComponent } = await import('vue')
  return { default: defineComponent({ props: ['icon', 'onUpload', 'onGenerate'], emits: ['update:icon'], template: '<div />' }) }
})
vi.mock('@/hooks/use-upload-file', async () => {
  const { ref } = await import('vue')
  return { useUploadImage: () => { const image_url = ref(''); mocks.imageUrl = image_url; return { image_url, handleUploadImage: mocks.upload } } }
})
vi.mock('@/hooks/use-tool', async () => {
  const { ref } = await import('vue')
  const state = () => ({ loading: ref(false) })
  return {
    useGetApiToolProvider: () => ({ ...state(), api_tool_provider: ref({ headers: [] }), loadApiToolProvider: mocks.loadProvider }),
    useGetApiToolProvidersWithPage: () => ({ ...state(), paginator: ref({ current_page: 1, total_page: 1 }), api_tool_providers: ref(mocks.providers), loadApiToolProviders: mocks.loadProviders }),
    useDeleteApiToolProvider: () => ({ handleDelete: vi.fn() }), useUpdateApiToolProvider: () => ({ ...state(), handleUpdateApiToolProvider: vi.fn() }),
    useCreateApiToolProvider: () => ({ ...state(), handleCreateApiToolProvider: vi.fn() }), useValidateOpenAPISchema: () => ({ handleValidateOpenAPISchema: mocks.validateOpenapi }),
    useRegenerateIcon: () => ({ ...state(), handleRegenerateIcon: vi.fn() }), useGenerateIconPreview: () => ({ ...state(), handleGenerateIconPreview: mocks.generatePreview }),
  }
})

const IconStub = defineComponent({ props: ['icon', 'onUpload', 'onGenerate'], emits: ['update:icon'], template: '<div />' })
const ModalStub = defineComponent({ props: ['visible'], emits: ['cancel'], template: '<div v-if="visible"><slot /><button data-cancel @click="$emit(\'cancel\')">close</button></div>' })
const DrawerStub = defineComponent({ props: ['visible'], emits: ['cancel'], template: '<div v-if="visible"><slot /><button data-drawer-cancel @click="$emit(\'cancel\')">close</button></div>' })
const FormStub = { template: '<div><slot /></div>', methods: { resetFields() {} } }
const deferred = () => { let resolve!: () => void; const promise = new Promise<void>(done => { resolve = done }); return { promise, resolve } }
const setupProviderListMocks = () => {
  mocks.route = reactive({ path: '/space/tools', query: {} })
  mocks.providers = [{ id: 'provider-1', name: 'Provider', description: '', icon: '', tools: [], created_at: 0 }]
  mocks.loadProviders.mockReset().mockResolvedValue(undefined)
  mocks.error.mockReset()
}

describe('space tools icon upload lifecycle', () => {
  it('reports provider detail failures without opening the editor', async () => {
    setupProviderListMocks()
    mocks.loadProvider.mockReset().mockRejectedValueOnce(new Error('details unavailable'))
    const wrapper = mount(ToolListView, { global: { stubs: { 'a-modal': ModalStub, 'a-drawer': DrawerStub, 'a-form': FormStub, 'a-form-item': FormStub, 'a-spin': FormStub, IconUploadGenerator: IconStub } } })
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    state.showIdx = 0
    await nextTick()

    let rejected = false
    try { await state.handleUpdate() } catch (_error) { rejected = true }

    expect(rejected).toBe(false)
    expect(mocks.error).toHaveBeenCalledWith('details unavailable')
    expect(state.showUpdateModal).toBe(false)
    wrapper.unmount()
  })

  it('ignores provider detail failures after the drawer is canceled', async () => {
    let rejectDetails!: (error: Error) => void
    const pending = new Promise<void>((_, reject) => { rejectDetails = reject })
    setupProviderListMocks()
    mocks.loadProvider.mockReset().mockReturnValueOnce(pending)
    const wrapper = mount(ToolListView, { global: { stubs: { 'a-modal': ModalStub, 'a-drawer': DrawerStub, 'a-form': FormStub, 'a-form-item': FormStub, 'a-spin': FormStub, IconUploadGenerator: IconStub } } })
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    state.showIdx = 0
    await nextTick()
    const edit = state.handleUpdate()

    await wrapper.find('[data-drawer-cancel]').trigger('click')
    rejectDetails(new Error('late details failure'))
    let rejected = false
    try { await edit } catch (_error) { rejected = true }

    expect(rejected).toBe(false)
    expect(mocks.error).not.toHaveBeenCalled()
    expect(state.showUpdateModal).toBe(false)
    wrapper.unmount()
  })
  it('reports provider list failures and ignores late scroll errors after unmount', async () => {
    let rejectLateLoad!: (error: Error) => void
    const lateLoad = new Promise<void>((_, reject) => { rejectLateLoad = reject })
    mocks.route = reactive({ path: '/space/tools', query: {} })
    mocks.loadProviders.mockReset().mockRejectedValueOnce(new Error('network unavailable')).mockReturnValueOnce(lateLoad)
    mocks.error.mockReset()
    const wrapper = mount(ToolListView, { global: { stubs: { 'a-modal': ModalStub, 'a-drawer': DrawerStub, 'a-form': FormStub, 'a-form-item': FormStub, 'a-spin': FormStub, IconUploadGenerator: IconStub } } })
    await flushPromises()

    expect(mocks.error).toHaveBeenCalledWith('network unavailable')
    const state = (wrapper.vm.$ as any).setupState
    state.handleScroll({ target: { scrollTop: 90, scrollHeight: 100, clientHeight: 20 } })
    wrapper.unmount()
    rejectLateLoad(new Error('late failure'))
    await flushPromises()
    expect(mocks.error).toHaveBeenCalledTimes(1)
  })

  it('ignores OpenAPI assistant chunks and results after canceling the form', async () => {
    let resolve!: (value: Record<string, never>) => void
    let onData!: (event: Record<string, any>) => void
    let signal!: AbortSignal
    const pending = new Promise<Record<string, never>>(done => { resolve = done })
    mocks.route = reactive({ path: '/space/tools', query: { create_type: 'tool' } })
    mocks.openapiSchemaAssistantChat.mockReset().mockImplementation((_question: string, callback: typeof onData, requestSignal: AbortSignal) => {
      onData = callback
      signal = requestSignal
      return pending
    })
    mocks.validateOpenapi.mockResolvedValue(true)
    mocks.success.mockReset()
    const wrapper = mount(ToolListView, { global: { stubs: { 'a-modal': ModalStub, 'a-drawer': DrawerStub, 'a-form': FormStub, 'a-form-item': FormStub, 'a-spin': FormStub, IconUploadGenerator: IconStub } } })
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    state.openapiAssistantQuestion = 'Create a schema'
    const oldGeneration = state.handleGenerateOpenapiSchemaByAI()

    state.handleCancel()
    expect(signal.aborted).toBe(true)
    mocks.route.query = { create_type: 'tool' }
    await flushPromises()
    state.form.openapi_schema = 'new form schema'
    onData({ data: { content: '{"openapi":"3.0.0","paths":{}}' } })
    resolve({})
    await oldGeneration

    expect(state.form.openapi_schema).toBe('new form schema')
    expect(mocks.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('uses an empty search when route navigation removes the query', async () => {
    mocks.route = reactive({ path: '/space/tools', query: { search_word: 'northwind' } })
    mocks.loadProviders.mockReset()
    const wrapper = mount(ToolListView, { global: { stubs: { 'a-modal': ModalStub, 'a-drawer': DrawerStub, 'a-form': FormStub, 'a-form-item': FormStub, 'a-spin': FormStub, IconUploadGenerator: IconStub } } })
    await flushPromises()

    mocks.loadProviders.mockClear()
    mocks.route.query = {}
    await flushPromises()

    expect(mocks.loadProviders).toHaveBeenCalledWith(true, '')
    wrapper.unmount()
  })

  it('does not apply icon generation from a canceled form to a reopened tool form', async () => {
    const pending = deferred()
    mocks.route = reactive({ path: '/space/tools', query: { create_type: 'tool' } })
    mocks.generatePreview.mockReset().mockImplementation(async () => { await pending.promise; return 'old-icon' })
    mocks.success.mockReset()
    const wrapper = mount(ToolListView, { global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': FormStub, 'a-spin': FormStub, IconUploadGenerator: IconStub } } })
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    state.form.name = 'Old tool'
    const generate = wrapper.findComponent(IconStub).props('onGenerate') as () => Promise<void>
    const oldGeneration = generate()

    state.handleCancel()
    await flushPromises()
    mocks.route.query = { create_type: 'tool' }
    await nextTick()
    await flushPromises()
    state.form.name = 'New tool'
    state.form.icon = 'new-icon'
    pending.resolve()
    await oldGeneration

    expect(state.form.icon).toBe('new-icon')
    expect(mocks.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('invalidates icon error notifications after the create modal is canceled', async () => {
    let reject!: (error: Error) => void
    const pending = new Promise<string>((_, rejectPromise) => { reject = rejectPromise })
    mocks.route = reactive({ path: '/space/tools', query: { create_type: 'tool' } })
    mocks.generatePreview.mockReset().mockReturnValueOnce(pending)
    const wrapper = mount(ToolListView, { global: { stubs: { 'a-modal': ModalStub, 'a-drawer': DrawerStub, 'a-form': FormStub, 'a-form-item': FormStub, 'a-spin': FormStub, IconUploadGenerator: IconStub } } })
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    state.form.name = 'Old tool'
    const staleGeneration = state.handleGenerateIcon()
    await wrapper.find('[data-cancel]').trigger('click')
    const shouldNotifyError = mocks.generatePreview.mock.calls[0]?.[2] as () => boolean
    expect(shouldNotifyError()).toBe(false)
    reject(new Error('generation failed'))
    await staleGeneration
    wrapper.unmount()
  })

  it('does not apply an upload from a closed modal to a reopened tool form', async () => {
    const pending = deferred()
    mocks.route = reactive({ path: '/space/tools', query: { create_type: 'tool' } })
    mocks.upload.mockReset().mockImplementation(async () => { await pending.promise; mocks.imageUrl.value = 'old-icon' })
    const wrapper = mount(ToolListView, { global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': FormStub, 'a-spin': FormStub, IconUploadGenerator: IconStub } } })
    await flushPromises()
    const upload = wrapper.findComponent(IconStub).props('onUpload') as (file: File) => Promise<void>
    const oldUpload = upload(new File(['old'], 'old.png'))
    await wrapper.find('[data-cancel]').trigger('click')
    mocks.route.query = { create_type: 'tool' }
    await nextTick()
    wrapper.findComponent(IconStub).vm.$emit('update:icon', 'new-icon')
    pending.resolve()
    await oldUpload
    expect(wrapper.findComponent(IconStub).props('icon')).toBe('new-icon')
    wrapper.unmount()
  })

  it('keeps a canceled provider edit closed when its detail request completes', async () => {
    const pending = deferred()
    mocks.route = reactive({ path: '/space/tools', query: {} })
    mocks.providers = [{ id: 'provider-1', name: 'Provider', description: '', icon: '', tools: [], created_at: 0 }]
    mocks.loadProvider.mockReset().mockReturnValueOnce(pending.promise)
    const wrapper = mount(ToolListView, { global: { stubs: { 'a-modal': ModalStub, 'a-drawer': DrawerStub, 'a-form': FormStub, 'a-form-item': FormStub, 'a-spin': FormStub, IconUploadGenerator: IconStub } } })
    const state = (wrapper.vm.$ as any).setupState
    state.showIdx = 0
    await nextTick()
    const edit = state.handleUpdate()

    await wrapper.find('[data-drawer-cancel]').trigger('click')
    pending.resolve()
    await edit

    expect(state.showUpdateModal).toBe(false)
    wrapper.unmount()
  })

  it('does not report upload success after the tools view unmounts', async () => {
    const pending = deferred()
    mocks.route = reactive({ path: '/space/tools', query: { create_type: 'tool' } })
    mocks.success.mockReset()
    mocks.upload.mockReset().mockImplementation(async () => {
      await pending.promise
      mocks.imageUrl.value = 'late-icon'
    })
    const wrapper = mount(ToolListView, { global: { stubs: { 'a-modal': ModalStub, 'a-drawer': DrawerStub, 'a-form': FormStub, 'a-form-item': FormStub, 'a-spin': FormStub, IconUploadGenerator: IconStub } } })
    await flushPromises()
    const upload = wrapper.findComponent(IconStub).props('onUpload') as (file: File) => Promise<void>
    const oldUpload = upload(new File(['old'], 'old.png'))

    wrapper.unmount()
    pending.resolve()
    await oldUpload

    expect(mocks.success).not.toHaveBeenCalled()
  })

  it('does not open a provider editor after the tools view unmounts', async () => {
    const pending = deferred()
    mocks.route = reactive({ path: '/space/tools', query: {} })
    mocks.providers = [{ id: 'provider-1', name: 'Provider', description: '', icon: '', tools: [], created_at: 0 }]
    mocks.loadProvider.mockReset().mockReturnValueOnce(pending.promise)
    const wrapper = mount(ToolListView, { global: { stubs: { 'a-modal': ModalStub, 'a-drawer': DrawerStub, 'a-form': FormStub, 'a-form-item': FormStub, 'a-spin': FormStub, IconUploadGenerator: IconStub } } })
    const state = (wrapper.vm.$ as any).setupState
    state.showIdx = 0
    await nextTick()
    const edit = state.handleUpdate()

    wrapper.unmount()
    pending.resolve()
    await edit

    expect(state.showUpdateModal).toBe(false)
  })
})
