import { ref } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import PromptCompareModelConfigTrigger from '../PromptCompareModelConfigTrigger.vue'

const mocks = vi.hoisted(() => ({ languageModel: null as any, loading: null as any, load: vi.fn(), loadModels: vi.fn().mockResolvedValue(undefined), messageError: vi.fn() }))
vi.mock('@/hooks/use-language-model', async () => {
  const { ref } = await import('vue')
  return {
    useGetLanguageModel: () => ({ language_model: mocks.languageModel, loading: mocks.loading, loadLanguageModel: mocks.load }),
    useGetLanguageModels: () => ({ language_models: ref([]), loadLanguageModels: mocks.loadModels }),
  }
})
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.messageError } }))

it('does not apply a model while its defaults are still loading', async () => {
  let finishLoad!: () => void
  mocks.loadModels.mockReset().mockResolvedValue(undefined)
  mocks.loading = ref(false)
  mocks.languageModel = ref({ parameters: [{ name: 'temperature', default: 0.9 }] })
  mocks.load.mockReset().mockResolvedValueOnce(true).mockImplementationOnce(() => {
    mocks.loading.value = true
    return new Promise<boolean>((resolve) => {
      finishLoad = () => {
        mocks.languageModel.value = { parameters: [{ name: 'temperature', default: 0.2 }] }
        mocks.loading.value = false
        resolve(true)
      }
    })
  })
  const wrapper = shallowMount(PromptCompareModelConfigTrigger, {
    props: { model_config: { provider: 'old', model: 'old-model', parameters: { temperature: 0.9 } } },
  })
  await flushPromises()
  const state = (wrapper.vm.$ as any).setupState
  state.form.selectValue = 'new/new-model'
  state.changeModel('new/new-model')
  state.handleApply()

  expect(wrapper.emitted('update:model_config')).toBeUndefined()
  finishLoad()
  await flushPromises()
  state.handleApply()
  expect(wrapper.emitted('update:model_config')?.[0][0]).toEqual({
    provider: 'new', model: 'new-model', parameters: { temperature: 0.2 },
  })
  wrapper.unmount()
})

it('reverts a model selection when its defaults fail to load', async () => {
  const requests: { resolve: (isLatest: boolean) => void; reject: (error: Error) => void }[] = []
  mocks.loadModels.mockReset().mockResolvedValue(undefined)
  mocks.loading = ref(false)
  mocks.languageModel = ref({ parameters: [{ name: 'temperature', default: 0.9 }] })
  mocks.load.mockReset().mockResolvedValueOnce(true).mockImplementation(() => new Promise((resolve, reject) => requests.push({ resolve, reject })))
  mocks.messageError.mockReset()
  const wrapper = shallowMount(PromptCompareModelConfigTrigger, {
    props: { model_config: { provider: 'old', model: 'old-model', parameters: { temperature: 0.9 } } },
  })
  await flushPromises()
  const state = (wrapper.vm.$ as any).setupState
  state.form.selectValue = 'new/new-model'
  state.changeModel('new/new-model')
  state.form.selectValue = 'other/other-model'
  state.changeModel('other/other-model')
  state.form.selectValue = 'new/new-model'
  state.changeModel('new/new-model')
  requests[0].reject(new Error('stale model defaults unavailable'))
  await flushPromises()
  expect(state.form.selectValue).toBe('new/new-model')
  expect(mocks.messageError).not.toHaveBeenCalled()
  requests[1].resolve(false)
  requests[2].reject(new Error('model defaults unavailable'))
  await flushPromises()
  state.handleApply()

  expect(wrapper.emitted('update:model_config')?.[0][0]).toEqual({
    provider: 'old', model: 'old-model', parameters: { temperature: 0.9 },
  })
  expect(mocks.messageError).toHaveBeenCalledWith('model defaults unavailable')
  wrapper.unmount()
})

it('reports model option load failures and ignores them after unmount', async () => {
  mocks.loading = ref(false)
  mocks.languageModel = ref({ parameters: [] })
  mocks.load.mockReset()
  mocks.messageError.mockReset()
  mocks.loadModels.mockReset().mockRejectedValueOnce(new Error('model list unavailable'))
  const wrapper = shallowMount(PromptCompareModelConfigTrigger, { props: { model_config: {} } })
  await flushPromises()
  expect(mocks.messageError).toHaveBeenCalledWith('model list unavailable')
  wrapper.unmount()

  let rejectLoad!: (error: Error) => void
  mocks.loadModels.mockReset().mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectLoad = reject }))
  const unmountedWrapper = shallowMount(PromptCompareModelConfigTrigger, { props: { model_config: {} } })
  unmountedWrapper.unmount()
  mocks.messageError.mockReset()
  rejectLoad(new Error('late model list failure'))
  await flushPromises()
  expect(mocks.messageError).not.toHaveBeenCalled()
})
