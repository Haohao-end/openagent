import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, reactive } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import DatasetListView from '@/views/space/datasets/ListView.vue'
import IconUploadGenerator from '@/components/IconUploadGenerator.vue'

const mocks = vi.hoisted(() => ({ route: null as any, form: null as any, imageUrl: null as any, loadDataset: vi.fn(), loadDatasets: vi.fn(), saveDataset: vi.fn(), uploadImage: vi.fn(), generateIconPreview: vi.fn(), success: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ push: vi.fn(), replace: (target: any) => Object.assign(mocks.route, target) }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/stores/account', () => ({ useAccountStore: () => ({ account: { avatar: '', name: 'Owner' } }) }))
vi.mock('@/utils/helper', () => ({ getUserAvatarUrl: () => '' }))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: mocks.success, warning: vi.fn() } }))
vi.mock('@/components/IconUploadGenerator.vue', async () => {
  const { defineComponent } = await import('vue')
  return { default: defineComponent({ name: 'IconUploadGenerator', props: ['icon', 'onUpload', 'fileList', 'name', 'description', 'loading', 'placeholder'], emits: ['update:icon'], template: '<div />' }) }
})
vi.mock('@/hooks/use-upload-file', async () => {
  const { ref } = await import('vue')
  return { useUploadImage: () => { const image_url = ref(''); mocks.imageUrl = image_url; return { image_url, handleUploadImage: mocks.uploadImage } } }
})
vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return {
    useCreateOrUpdateDataset: () => { const form = ref({ fileList: [], icon: '', name: '', description: '' }); mocks.form = form; const showUpdateModal = ref(false); mocks.saveDataset = vi.fn(); return { loading: ref(false), form, formRef: ref(), saveDataset: mocks.saveDataset, showUpdateModal, updateShowUpdateModal: (visible: boolean, callback?: () => void) => { showUpdateModal.value = visible; callback?.() } } },
    useDeleteDataset: () => ({ handleDelete: vi.fn() }),
    useGenerateIconPreview: () => ({ loading: ref(false), handleGenerateIconPreview: mocks.generateIconPreview }),
    useGetDataset: () => ({ dataset: ref({}), loadDataset: mocks.loadDataset }),
    useGetDatasetsWithPage: () => ({ loading: ref(false), datasets: ref([]), paginator: ref({ current_page: 1, total_page: 1 }), loadDatasets: mocks.loadDatasets }),
    useRegenerateIcon: () => ({ loading: ref(false), handleRegenerateIcon: vi.fn() }),
  }
})

const SlotStub = { template: '<div><slot /></div>' }
const FormStub = defineComponent({ setup: (_, { expose, slots }) => { expose({ resetFields: vi.fn() }); return () => h('div', slots.default?.()) } })
const ModalStub = defineComponent({ props: ['visible'], emits: ['cancel'], template: '<div v-if="visible"><slot /><button data-cancel @click="$emit(\'cancel\')">close</button></div>' })
const deferred = () => { let resolve!: () => void; const promise = new Promise<void>(done => { resolve = done }); return { promise, resolve } }
const deferredValue = () => { let resolve!: (value: string) => void; const promise = new Promise<string>(done => { resolve = done }); return { promise, resolve } }

describe('dataset icon upload lifecycle', () => {
  it('uses an empty search when browser navigation removes the route query', async () => {
    mocks.route = reactive({ path: '/space/datasets', query: { search_word: 'northwind' } })
    mocks.loadDatasets.mockReset()
    const wrapper = mount(DatasetListView, { global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': SlotStub, 'a-spin': SlotStub } } })
    await flushPromises()

    mocks.loadDatasets.mockClear()
    mocks.route.query = {}
    await flushPromises()

    expect(mocks.loadDatasets).toHaveBeenCalledWith(true, '')
    wrapper.unmount()
  })

  it('does not apply an upload from a closed create modal to a new form', async () => {
    const pending = deferred()
    mocks.route = reactive({ path: '/space/datasets', query: { create_type: 'dataset' } })
    mocks.uploadImage.mockReset().mockImplementation(async () => { await pending.promise; mocks.imageUrl.value = 'icon-from-old-form' })
    const wrapper = mount(DatasetListView, { global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': SlotStub, 'a-spin': SlotStub } } })
    await flushPromises()

    const upload = wrapper.findComponent(IconUploadGenerator).props('onUpload') as (file: File) => Promise<void>
    const staleUpload = upload(new File(['icon'], 'icon.png'))
    await wrapper.find('[data-cancel]').trigger('click')
    await flushPromises()
    mocks.route.query = { create_type: 'dataset' }
    await flushPromises()
    wrapper.findComponent(IconUploadGenerator).vm.$emit('update:icon', 'icon-from-new-form')

    pending.resolve()
    await staleUpload
    expect(mocks.form.value.icon).toBe('icon-from-new-form')
    wrapper.unmount()
  })

  it('does not apply icon generation from a closed create modal to a new form', async () => {
    const pending = deferredValue()
    mocks.route = reactive({ path: '/space/datasets', query: { create_type: 'dataset' } })
    mocks.generateIconPreview.mockReset().mockReturnValueOnce(pending.promise)
    const wrapper = mount(DatasetListView, { global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': SlotStub, 'a-spin': SlotStub } } })
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    state.form.name = 'Old dataset'
    const staleGeneration = state.handleGenerateIcon()

    await wrapper.find('[data-cancel]').trigger('click')
    await flushPromises()
    mocks.route.query = { create_type: 'dataset' }
    await flushPromises()
    state.form.name = 'New dataset'
    state.form.icon = 'icon-from-new-form'
    pending.resolve('icon-from-old-form')
    await staleGeneration

    expect(mocks.form.value.icon).toBe('icon-from-new-form')
    wrapper.unmount()
  })

  it('does not report a stale icon generation failure after canceling the modal', async () => {
    let reject!: (error: Error) => void
    const pending = new Promise<string>((_, rejectPromise) => { reject = rejectPromise })
    mocks.route = reactive({ path: '/space/datasets', query: { create_type: 'dataset' } })
    mocks.generateIconPreview.mockReset().mockReturnValueOnce(pending)
    const wrapper = mount(DatasetListView, { global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': SlotStub, 'a-spin': SlotStub } } })
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    state.form.name = 'Old dataset'
    const staleGeneration = state.handleGenerateIcon()
    await wrapper.find('[data-cancel]').trigger('click')
    const shouldNotifyError = mocks.generateIconPreview.mock.calls[0]?.[2] as () => boolean
    expect(shouldNotifyError()).toBe(false)
    reject(new Error('generation failed'))
    await staleGeneration

    wrapper.unmount()
  })

  it('ignores an edit detail response after canceling into a create form', async () => {
    let resolve!: (value: Record<string, string>) => void
    const pending = new Promise<Record<string, string>>(done => { resolve = done })
    mocks.route = reactive({ path: '/space/datasets', query: {} })
    mocks.loadDataset.mockReset().mockReturnValueOnce(pending)
    mocks.saveDataset.mockReset()
    const wrapper = mount(DatasetListView, { global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': SlotStub, 'a-spin': SlotStub } } })
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    state.handleUpdate('dataset-a')
    await flushPromises()

    await state.handleCancel()
    mocks.route.query = { create_type: 'dataset' }
    await flushPromises()
    state.form.name = 'New dataset'
    state.form.description = 'New description'
    resolve({ icon: 'old-icon', name: 'Old dataset', description: 'Old description' })
    await flushPromises()

    expect(mocks.form.value.name).toBe('New dataset')
    await state.handleSubmit({ errors: undefined })
    expect(mocks.saveDataset).toHaveBeenCalledWith('')
    wrapper.unmount()
  })

  it('does not report upload success after the datasets view unmounts', async () => {
    const pending = deferred()
    mocks.route = reactive({ path: '/space/datasets', query: { create_type: 'dataset' } })
    mocks.success.mockReset()
    mocks.uploadImage.mockReset().mockImplementation(async () => { await pending.promise; mocks.imageUrl.value = 'late-icon' })
    const wrapper = mount(DatasetListView, { global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': SlotStub, 'a-spin': SlotStub } } })
    await flushPromises()
    const upload = wrapper.findComponent(IconUploadGenerator).props('onUpload') as (file: File) => Promise<void>
    const staleUpload = upload(new File(['icon'], 'icon.png'))

    wrapper.unmount()
    pending.resolve()
    await staleUpload

    expect(mocks.success).not.toHaveBeenCalled()
  })
})
