import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'
import ModelConfig from '../ModelConfig.vue'

const mocks = vi.hoisted(() => ({
  languageModel: null as any,
  loadLanguageModel: vi.fn(),
  updateDraft: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/hooks/use-language-model', () => ({
  useGetLanguageModel: () => ({ loading: ref(false), language_model: mocks.languageModel, loadLanguageModel: mocks.loadLanguageModel }),
  useGetLanguageModels: () => ({ language_models: ref([]), loadLanguageModels: vi.fn() }),
}))
vi.mock('@/hooks/use-app', () => ({ useUpdateDraftAppConfig: () => ({ handleUpdateDraftAppConfig: mocks.updateDraft }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

const TriggerStub = defineComponent({ emits: ['hide'], template: '<div><slot /><slot name="content" /></div>' })
const SelectStub = defineComponent({ props: ['modelValue'], emits: ['update:modelValue', 'change'], template: '<div />' })
const deferred = () => {
  let resolve!: () => void
  const promise = new Promise<void>(done => { resolve = done })
  return { promise, resolve }
}

describe('ModelConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.updateDraft.mockResolvedValue(undefined)
    mocks.languageModel = ref({ parameters: [] })
    mocks.loadLanguageModel.mockImplementation(async (_provider: string, model: string) => {
      if (model === 'new-model') await pendingLoad.promise
      mocks.languageModel.value = { parameters: [{ name: 'temperature', default: 0.2 }] }
    })
  })

  const pendingLoad = deferred()

  it('waits for the selected model defaults before saving the draft', async () => {
    const wrapper = mount(ModelConfig, {
      props: { app_id: 'app-1', model_config: { provider: 'old', model: 'old-model', parameters: { temperature: 0.9 } }, dialog_round: 3 },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    await flushPromises()
    const select = wrapper.findComponent(SelectStub)
    select.vm.$emit('update:modelValue', 'new/new-model')
    select.vm.$emit('change', 'new/new-model')
    wrapper.findComponent(TriggerStub).vm.$emit('hide')
    await flushPromises()

    expect(mocks.updateDraft).not.toHaveBeenCalled()
    pendingLoad.resolve()
    await flushPromises()
    expect(mocks.updateDraft).toHaveBeenCalledWith('app-1', expect.objectContaining({
      model_config: { provider: 'new', model: 'new-model', parameters: { temperature: 0.2 } },
    }))
    wrapper.unmount()
  })
})
