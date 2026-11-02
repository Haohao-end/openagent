import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, reactive } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import DatasetListView from '@/views/space/datasets/ListView.vue'
import IconUploadGenerator from '@/components/IconUploadGenerator.vue'

const mocks = vi.hoisted(() => ({ route: null as any, form: null as any, imageUrl: null as any, uploadImage: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ push: vi.fn(), replace: (target: any) => Object.assign(mocks.route, target) }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/stores/account', () => ({ useAccountStore: () => ({ account: { avatar: '', name: 'Owner' } }) }))
vi.mock('@/utils/helper', () => ({ getUserAvatarUrl: () => '' }))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn(), warning: vi.fn() } }))
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
    useCreateOrUpdateDataset: () => { const form = ref({ fileList: [], icon: '', name: '', description: '' }); mocks.form = form; return { loading: ref(false), form, formRef: ref(), saveDataset: vi.fn(), showUpdateModal: ref(false), updateShowUpdateModal: vi.fn() } },
    useDeleteDataset: () => ({ handleDelete: vi.fn() }),
    useGenerateIconPreview: () => ({ loading: ref(false), handleGenerateIconPreview: vi.fn() }),
    useGetDataset: () => ({ dataset: ref({}), loadDataset: vi.fn() }),
    useGetDatasetsWithPage: () => ({ loading: ref(false), datasets: ref([]), paginator: ref({ current_page: 1, total_page: 1 }), loadDatasets: vi.fn() }),
    useRegenerateIcon: () => ({ loading: ref(false), handleRegenerateIcon: vi.fn() }),
  }
})

const SlotStub = { template: '<div><slot /></div>' }
const ModalStub = defineComponent({ props: ['visible'], emits: ['cancel'], template: '<div v-if="visible"><slot /><button data-cancel @click="$emit(\'cancel\')">close</button></div>' })
const deferred = () => { let resolve!: () => void; const promise = new Promise<void>(done => { resolve = done }); return { promise, resolve } }

describe('dataset icon upload lifecycle', () => {
  it('does not apply an upload from a closed create modal to a new form', async () => {
    const pending = deferred()
    mocks.route = reactive({ path: '/space/datasets', query: { create_type: 'dataset' } })
    mocks.uploadImage.mockReset().mockImplementation(async () => { await pending.promise; mocks.imageUrl.value = 'icon-from-old-form' })
    const wrapper = mount(DatasetListView, { global: { stubs: { 'a-modal': ModalStub, 'a-form': SlotStub, 'a-form-item': SlotStub, 'a-spin': SlotStub } } })
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
})
