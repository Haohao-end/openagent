import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import PromptCompareView from '../PromptCompareView.vue'
const mocks = vi.hoisted(() => ({
  route: { params: { app_id: 'app-1' } },
  ssePost: vi.fn(),
  signals: [] as AbortSignal[],
  loadDraftAppConfig: vi.fn(),
  updateDraftAppConfig: vi.fn(),
  messageError: vi.fn(),
  messageWarning: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route })); vi.mock('@/utils/request', () => ({ get: vi.fn(), post: vi.fn(), ssePost: mocks.ssePost }))
vi.mock('@/hooks/use-app', () => ({
  useGetDraftAppConfig: () => ({ draftAppConfigForm: { value: { model_config: { provider: 'p', model: 'm', parameters: {} }, preset_prompt: 'prompt' } }, loadDraftAppConfig: mocks.loadDraftAppConfig }),
  useUpdateDraftAppConfig: () => ({ handleUpdateDraftAppConfig: mocks.updateDraftAppConfig }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) })); vi.mock('@/stores/account', () => ({ useAccountStore: () => ({ account: {} }) })); vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.messageError, warning: mocks.messageWarning } }))

beforeEach(() => {
  mocks.loadDraftAppConfig.mockReset().mockResolvedValue(undefined)
  mocks.messageError.mockReset()
  mocks.messageWarning.mockReset()
  mocks.ssePost.mockReset()
  mocks.signals.length = 0
})

it('reports draft configuration load failures instead of rejecting the mount hook', async () => {
  mocks.loadDraftAppConfig.mockRejectedValueOnce('private draft response details')
  const errors: unknown[] = []
  const wrapper = shallowMount(PromptCompareView, {
    props: { app: { id: 'app-1', name: 'App' } },
    global: { config: { errorHandler: (error) => errors.push(error) } },
  })

  await flushPromises()

  expect(mocks.messageError).toHaveBeenCalledWith('appStudio.promptCompare.configLoadFailed')
  expect(errors).toEqual([])
  wrapper.unmount()
})

it('does not report a draft load failure after the page unmounts', async () => {
  let rejectLoad!: (error: Error) => void
  mocks.loadDraftAppConfig.mockReturnValueOnce(new Promise((_resolve, reject) => { rejectLoad = reject }))
  const wrapper = shallowMount(PromptCompareView, { props: { app: { id: 'app-1', name: 'App' } } })

  await flushPromises()
  wrapper.unmount()
  rejectLoad(new Error('late draft load failure'))
  await flushPromises()

  expect(mocks.messageError).not.toHaveBeenCalled()
})

it('aborts both prompt comparison streams when the page unmounts', async () => {
  mocks.ssePost.mockImplementation((_url, options) => {
    mocks.signals.push(options.signal)
    return new Promise<void>((_resolve, reject) => options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true }))
  })
  const wrapper = shallowMount(PromptCompareView, { props: { app: { id: 'app-1', name: 'App' } } })
  await flushPromises()
  await wrapper.get('textarea').setValue('hello'); await wrapper.get('textarea').trigger('keydown.enter')
  await flushPromises(); wrapper.unmount()
  expect(mocks.signals).toHaveLength(2); expect(mocks.signals.every((signal) => signal?.aborted)).toBe(true)
})

it('does not mark preset prompt applied when draft app config update fails', async () => {
  const errors: unknown[] = []
  mocks.updateDraftAppConfig.mockRejectedValueOnce(new Error('Update failed'))
  const wrapper = shallowMount(PromptCompareView, {
    props: { app: { id: 'app-1', name: 'App' } },
    global: { config: { errorHandler: (error) => errors.push(error) } },
  })
  await flushPromises()
  const state = (wrapper.vm.$ as any).setupState
  const candidateLane = state.lanes.find((lane: any) => lane.key === 'candidate') || state.lanes[1]
  candidateLane.preset_prompt = 'candidate new prompt'

  await state.handleApplyPrompt(candidateLane)
  await flushPromises()

  expect(state.appliedPresetPrompt).toBe('prompt')
  expect(state.isAppliedPromptLane(candidateLane)).toBe(false)
  expect(errors).toEqual([])
  wrapper.unmount()
})

it('marks preset prompt applied when draft app config update succeeds', async () => {
  mocks.updateDraftAppConfig.mockResolvedValueOnce(undefined)
  const wrapper = shallowMount(PromptCompareView, { props: { app: { id: 'app-1', name: 'App' } } })
  await flushPromises()
  const state = (wrapper.vm.$ as any).setupState
  const candidateLane = state.lanes.find((lane: any) => lane.key === 'candidate') || state.lanes[1]
  candidateLane.preset_prompt = 'candidate new prompt'

  await state.handleApplyPrompt(candidateLane)
  await flushPromises()

  expect(mocks.updateDraftAppConfig).toHaveBeenCalledWith('app-1', {
    preset_prompt: 'candidate new prompt',
  })
  expect(state.appliedPresetPrompt).toBe('candidate new prompt')
  expect(state.isAppliedPromptLane(candidateLane)).toBe(true)
  wrapper.unmount()
})
