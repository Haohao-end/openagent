import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import CreateOrUpdateAppModal from '../CreateOrUpdateAppModal.vue'

const mocks = vi.hoisted(() => ({
  upload: vi.fn(),
  generate: vi.fn(),
  error: vi.fn(),
  success: vi.fn(),
  imageUrl: { value: '' },
}))

vi.mock('@/hooks/use-app', () => ({
  useCreateApp: () => ({ loading: false, handleCreateApp: vi.fn() }),
  useUpdateApp: () => ({ loading: false, handleUpdateApp: vi.fn() }),
  useGetApp: () => ({ app: { value: {} }, loading: { value: false }, loadApp: vi.fn() }),
  useRegenerateIcon: () => ({ loading: false, handleRegenerateIcon: vi.fn() }),
  useGenerateIconPreview: () => ({ loading: false, handleGenerateIconPreview: mocks.generate }),
}))

vi.mock('@/hooks/use-upload-file', () => ({
  useUploadImage: () => ({ image_url: mocks.imageUrl, handleUploadImage: mocks.upload }),
}))
vi.mock('@arco-design/web-vue', () => ({
  Message: { error: mocks.error, success: mocks.success, warning: vi.fn() },
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

const deferred = <T>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const mountModal = () => {
  const wrapper = shallowMount(CreateOrUpdateAppModal, {
    props: { app_id: '', visible: true },
  })
  const state = (wrapper.vm as any).$.setupState
  state.form.name = 'Agent'
  return { wrapper, state }
}

it.each([
  ['generation', 'upload', 'resolve'],
  ['upload', 'generation', 'resolve'],
  ['generation', 'upload', 'reject'],
  ['upload', 'generation', 'reject'],
] as const)(
  'keeps the newer %s/%s icon action result when the older request %s',
  async (firstAction, lastAction, staleOutcome) => {
    const generation = deferred<string>()
    const upload = deferred<string>()
    mocks.generate.mockImplementation(
      async (_name: string, _description: string, shouldNotify: () => boolean) => {
        try {
          return await generation.promise
        } catch (error) {
          if (shouldNotify()) mocks.error('generation failed')
          throw error
        }
      },
    )
    mocks.upload.mockImplementation(async () => {
      mocks.imageUrl.value = await upload.promise
    })
    const { wrapper, state } = mountModal()
    const actions = {
      generation: () => state.handleGenerateIcon(),
      upload: () => state.handleUploadIcon(new File(['icon'], 'icon.png')),
    }

    const first = actions[firstAction]()
    const last = actions[lastAction]()
    const expectedIcon = lastAction === 'upload' ? 'uploaded-icon' : 'generated-icon'
    if (lastAction === 'upload') upload.resolve(expectedIcon)
    else generation.resolve(expectedIcon)
    await last
    const staleRequest = firstAction === 'upload' ? upload : generation
    if (staleOutcome === 'reject') staleRequest.reject(new Error(`${firstAction} failed`))
    else staleRequest.resolve(firstAction === 'upload' ? 'uploaded-icon' : 'generated-icon')
    await first.catch(() => undefined)
    await flushPromises()

    expect(state.form.icon).toBe(expectedIcon)
    expect(state.form.fileList[0]?.url).toBe(expectedIcon)
    expect(mocks.error).not.toHaveBeenCalled()
    wrapper.unmount()
  },
)
