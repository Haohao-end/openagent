import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import ListView from '../ListView.vue'

const mocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  handleUploadImage: vi.fn(),
  handleCreateApiToolProvider: vi.fn(),
  handleGenerateIconPreview: vi.fn(),
  loadCategories: vi.fn(),
  loadBuiltinTools: vi.fn(),
}))

const imageUrl = ref('')
const createLoading = ref(false)
const validateLoading = ref(false)

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ query: {}, path: '/store/tools' }),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  }
})

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key, locale: ref('zh-CN') }),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: { success: mocks.success, error: mocks.error, warning: mocks.warning },
}))

vi.mock('@/hooks/use-builtin-tool', () => ({
  useGetCategories: () => ({ categories: ref([]), loadCategories: mocks.loadCategories }),
  useGetBuiltinTools: () => ({ loading: ref(false), builtin_tools: ref([]), loadBuiltinTools: mocks.loadBuiltinTools }),
}))

vi.mock('@/hooks/use-upload-file', () => ({
  useUploadImage: () => ({
    loading: ref(false),
    image_url: imageUrl,
    handleUploadImage: mocks.handleUploadImage,
  }),
}))

vi.mock('@/hooks/use-tool', () => ({
  useCreateApiToolProvider: () => ({
    loading: createLoading,
    handleCreateApiToolProvider: mocks.handleCreateApiToolProvider,
  }),
  useGenerateIconPreview: () => ({
    loading: ref(false),
    handleGenerateIconPreview: mocks.handleGenerateIconPreview,
  }),
  useValidateOpenAPISchema: () => ({
    loading: validateLoading,
    handleValidateOpenAPISchema: vi.fn(),
  }),
}))

describe('Store Tools ListView icon upload and submit guards', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    imageUrl.value = ''
    createLoading.value = false
    validateLoading.value = false
    mocks.loadCategories.mockResolvedValue(undefined)
    mocks.loadBuiltinTools.mockResolvedValue(undefined)
    mocks.handleCreateApiToolProvider.mockResolvedValue(true)
  })

  it('ignores stale icon upload after modal cancel', async () => {
    let resolveUpload!: () => void
    mocks.handleUploadImage.mockReturnValueOnce(
      new Promise<void>((resolve) => {
        resolveUpload = resolve
      }),
    )

    const wrapper = shallowMount(ListView)
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    state.formRef = { resetFields: vi.fn() }

    state.showCreateModal = true
    const uploadPromise = state.handleUploadIcon(new File([''], 'icon.png'))

    // Cancel modal while upload is in flight
    state.handleCreateCancel()
    expect(state.showCreateModal).toBe(false)
    expect(imageUrl.value).toBe('')

    // Late upload resolves
    imageUrl.value = 'https://example.com/stale-icon.png'
    resolveUpload()
    await uploadPromise
    await flushPromises()

    // Stale icon should NOT be applied to form
    expect(state.form.icon).toBe('')
    expect(mocks.success).not.toHaveBeenCalled()
  })

  it('guards against concurrent submit when createLoading is true', async () => {
    const wrapper = shallowMount(ListView)
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    state.formRef = { resetFields: vi.fn() }

    createLoading.value = true
    await state.handleCreateSubmit({
      values: { fileList: [], icon: 'icon.png', name: 'tool', openapi_schema: '', headers: [] },
      errors: undefined,
    })

    expect(mocks.handleCreateApiToolProvider).not.toHaveBeenCalled()
  })

  it('guards against concurrent submit when validateLoading is true', async () => {
    const wrapper = shallowMount(ListView)
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    state.formRef = { resetFields: vi.fn() }

    validateLoading.value = true
    await state.handleCreateSubmit({
      values: { fileList: [], icon: 'icon.png', name: 'tool', openapi_schema: '', headers: [] },
      errors: undefined,
    })

    expect(mocks.handleCreateApiToolProvider).not.toHaveBeenCalled()
  })
})
