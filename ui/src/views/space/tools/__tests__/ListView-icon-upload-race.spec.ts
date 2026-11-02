import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick, reactive } from 'vue'
import ToolListView from '../ListView.vue'

const mocks = vi.hoisted(() => ({ route: null as any, imageUrl: null as any, upload: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ replace: (target: any) => Object.assign(mocks.route, target) }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/stores/account', () => ({ useAccountStore: () => ({ account: { avatar: '', name: 'Owner' } }) }))
vi.mock('@/utils/helper', () => ({ getUserAvatarUrl: () => '' }))
vi.mock('@/services/ai', () => ({ openapiSchemaAssistantChat: vi.fn() }))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))
vi.mock('@/components/IconUploadGenerator.vue', async () => {
  const { defineComponent } = await import('vue')
  return { default: defineComponent({ props: ['icon', 'onUpload'], emits: ['update:icon'], template: '<div />' }) }
})
vi.mock('@/hooks/use-upload-file', async () => {
  const { ref } = await import('vue')
  return { useUploadImage: () => { const image_url = ref(''); mocks.imageUrl = image_url; return { image_url, handleUploadImage: mocks.upload } } }
})
vi.mock('@/hooks/use-tool', async () => {
  const { ref } = await import('vue')
  const state = () => ({ loading: ref(false) })
  return {
    useGetApiToolProvider: () => ({ ...state(), api_tool_provider: ref({}), loadApiToolProvider: vi.fn() }),
    useGetApiToolProvidersWithPage: () => ({ ...state(), paginator: ref({ current_page: 1, total_page: 1 }), api_tool_providers: ref([]), loadApiToolProviders: vi.fn() }),
    useDeleteApiToolProvider: () => ({ handleDelete: vi.fn() }), useUpdateApiToolProvider: () => ({ ...state(), handleUpdateApiToolProvider: vi.fn() }),
    useCreateApiToolProvider: () => ({ ...state(), handleCreateApiToolProvider: vi.fn() }), useValidateOpenAPISchema: () => ({ handleValidateOpenAPISchema: vi.fn() }),
    useRegenerateIcon: () => ({ ...state(), handleRegenerateIcon: vi.fn() }), useGenerateIconPreview: () => ({ ...state(), handleGenerateIconPreview: vi.fn() }),
  }
})

const IconStub = defineComponent({ props: ['icon', 'onUpload'], emits: ['update:icon'], template: '<div />' })
const ModalStub = defineComponent({ props: ['visible'], emits: ['cancel'], template: '<div v-if="visible"><slot /><button data-cancel @click="$emit(\'cancel\')">close</button></div>' })
const FormStub = { template: '<div><slot /></div>', methods: { resetFields() {} } }
const deferred = () => { let resolve!: () => void; const promise = new Promise<void>(done => { resolve = done }); return { promise, resolve } }

describe('space tools icon upload lifecycle', () => {
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
})
