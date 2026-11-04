import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import PromptCompareView from '../PromptCompareView.vue'
const mocks = vi.hoisted(() => ({ route: { params: { app_id: 'app-1' } }, ssePost: vi.fn(), signals: [] as AbortSignal[] }))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route })); vi.mock('@/utils/request', () => ({ get: vi.fn(), post: vi.fn(), ssePost: mocks.ssePost }))
vi.mock('@/hooks/use-app', () => ({
  useGetDraftAppConfig: () => ({ draftAppConfigForm: { value: { model_config: { provider: 'p', model: 'm', parameters: {} }, preset_prompt: 'prompt' } }, loadDraftAppConfig: vi.fn() }),
  useUpdateDraftAppConfig: () => ({ handleUpdateDraftAppConfig: vi.fn() }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) })); vi.mock('@/stores/account', () => ({ useAccountStore: () => ({ account: {} }) })); vi.mock('@arco-design/web-vue', () => ({ Message: { warning: vi.fn() } }))
it('aborts both prompt comparison streams when the page unmounts', async () => {
  mocks.signals.length = 0;
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
