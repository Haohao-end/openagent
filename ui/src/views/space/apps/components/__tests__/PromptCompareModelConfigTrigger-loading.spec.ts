import { ref } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import PromptCompareModelConfigTrigger from '../PromptCompareModelConfigTrigger.vue'

const mocks = vi.hoisted(() => ({ languageModel: null as any, loading: null as any, load: vi.fn() }))
vi.mock('@/hooks/use-language-model', async () => {
  const { ref } = await import('vue')
  return {
    useGetLanguageModel: () => ({ language_model: mocks.languageModel, loading: mocks.loading, loadLanguageModel: mocks.load }),
    useGetLanguageModels: () => ({ language_models: ref([]), loadLanguageModels: vi.fn() }),
  }
})
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

it('does not apply a model while its defaults are still loading', async () => {
  let finishLoad!: () => void
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
