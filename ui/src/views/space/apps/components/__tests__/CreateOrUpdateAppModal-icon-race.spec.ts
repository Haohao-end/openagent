import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import IconUploadGenerator from '@/components/IconUploadGenerator.vue'
import CreateOrUpdateAppModal from '../CreateOrUpdateAppModal.vue'

const mocks = vi.hoisted(() => ({
  upload: vi.fn(),
  generate: vi.fn(),
  error: vi.fn(),
  success: vi.fn(),
  imageUrl: { value: '' },
  app: { value: {} as any },
  loadApp: vi.fn(),
}))

vi.mock('@/hooks/use-app', () => ({
  useCreateApp: () => ({ loading: false, handleCreateApp: vi.fn() }),
  useUpdateApp: () => ({ loading: false, handleUpdateApp: vi.fn() }),
  useGetApp: () => ({ app: mocks.app, loading: { value: false }, loadApp: mocks.loadApp }),
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
    global: {
      stubs: { 'a-form': { methods: { resetFields: vi.fn() }, template: '<form><slot /></form>' } },
    },
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

it.each(
  ['generation', 'upload'].flatMap((action) =>
    ['resolve', 'reject'].map((outcome) => [action, outcome] as const),
  ),
)('ignores a pending %s request after the icon is deleted (%s)', async (action, outcome) => {
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
  state.form.icon = 'existing-icon'
  state.form.fileList = [{ uid: '1', name: 'icon', url: 'existing-icon' }]

  const pending =
    action === 'generation'
      ? state.handleGenerateIcon()
      : state.handleUploadIcon(new File(['icon'], 'icon.png'))
  const iconControl = wrapper.findComponent(IconUploadGenerator)
  iconControl.vm.$emit('update:icon', '')
  iconControl.vm.$emit('update:fileList', [])
  await nextTick()
  expect(iconControl.props('icon')).toBe('')
  expect(iconControl.props('fileList')).toEqual([])
  const request = action === 'generation' ? generation : upload
  if (outcome === 'reject') request.reject(new Error('request failed'))
  else request.resolve('late-icon')
  await pending.catch(() => undefined)
  await flushPromises()

  expect(state.form.icon).toBe('')
  expect(state.form.fileList).toEqual([])
  expect(mocks.error).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('ignores generation finishing after the modal closes and reopens', async () => {
  const generated = deferred<string>()
  mocks.generate.mockReturnValue(generated.promise)
  const { wrapper, state } = mountModal()
  const pending = state.handleGenerateIcon()

  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true })
  generated.resolve('stale-icon')
  await pending

  expect(state.form.icon).toBe('')
  wrapper.unmount()
})

it('keeps the new app icon when an earlier upload finishes after an app switch', async () => {
  const uploaded = deferred<string>()
  mocks.app.value = { icon: 'new-icon', name: 'New Agent', description: '' }
  mocks.upload.mockImplementation(async () => {
    mocks.imageUrl.value = await uploaded.promise
  })
  const { wrapper, state } = mountModal()
  const pending = state.handleUploadIcon(new File(['icon'], 'icon.png'))

  await wrapper.setProps({ app_id: 'new-app' })
  await flushPromises()
  uploaded.resolve('stale-icon')
  await pending

  expect(state.form.icon).toBe('new-icon')
  expect(state.form.fileList[0]?.url).toBe('new-icon')
  wrapper.unmount()
})

it('ignores generation finishing after the modal component unmounts', async () => {
  const generated = deferred<string>()
  mocks.generate.mockReturnValue(generated.promise)
  const { wrapper, state } = mountModal()
  const pending = state.handleGenerateIcon()

  wrapper.unmount()
  generated.resolve('stale-icon')
  await pending

  expect(state.form.icon).toBe('')
})
