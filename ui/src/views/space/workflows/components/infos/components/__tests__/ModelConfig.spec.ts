import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'
import ModelConfig from '../ModelConfig.vue'

const mocks = vi.hoisted(() => ({
  languageModel: null as any,
  loadLanguageModel: vi.fn(),
  loadLanguageModels: vi.fn(),
  messageError: vi.fn(),
}))
vi.mock('@/hooks/use-language-model', () => ({
  useGetLanguageModel: () => ({ loading: ref(false), language_model: mocks.languageModel, loadLanguageModel: mocks.loadLanguageModel }),
  useGetLanguageModels: () => ({ language_models: ref([]), loadLanguageModels: mocks.loadLanguageModels }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.messageError } }))

const TriggerStub = defineComponent({ emits: ['hide'], template: '<div><slot /><slot name="content" /></div>' })
const SelectStub = defineComponent({ props: ['modelValue'], emits: ['update:modelValue', 'change'], template: '<div />' })
const deferred = () => {
  let resolve!: () => void
  let reject!: (error: unknown) => void
  const promise = new Promise<void>((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}
const pendingLoad = deferred()

describe('Workflow ModelConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.languageModel = ref({ parameters: [] })
    mocks.loadLanguageModels.mockResolvedValue(undefined)
    mocks.loadLanguageModel.mockImplementation(async (_provider: string, model: string) => {
      if (model === 'new-model') await pendingLoad.promise
      mocks.languageModel.value = { parameters: [{ name: 'temperature', default: 0.2 }] }
      return true
    })
  })

  it('waits for the selected model defaults before emitting the config', async () => {
    const wrapper = mount(ModelConfig, {
      props: { model_config: { provider: 'old', model: 'old-model', parameters: { temperature: 0.9 } } },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    await flushPromises()
    const select = wrapper.findComponent(SelectStub)
    select.vm.$emit('update:modelValue', 'new/new-model')
    select.vm.$emit('change', 'new/new-model')
    wrapper.findComponent(TriggerStub).vm.$emit('hide')
    await flushPromises()

    expect(wrapper.emitted('update:model_config')).toBeUndefined()
    pendingLoad.resolve()
    await flushPromises()
    expect(wrapper.emitted('update:model_config')).toEqual([[{
      provider: 'new', model: 'new-model', parameters: { temperature: 0.2 },
    }]])
    wrapper.unmount()
  })

  it('reports a selected model load failure and does not emit a config', async () => {
    const error = new Error('model details unavailable')
    const wrapper = mount(ModelConfig, {
      props: { model_config: { provider: 'old', model: 'old-model', parameters: { temperature: 0.9 } } },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    await flushPromises()

    mocks.loadLanguageModel.mockRejectedValueOnce(error)
    wrapper.findComponent(SelectStub).vm.$emit('change', 'new/new-model')
    wrapper.findComponent(TriggerStub).vm.$emit('hide')
    await flushPromises()

    expect(mocks.messageError).toHaveBeenCalledWith('model details unavailable')
    expect(wrapper.emitted('update:model_config')).toBeUndefined()
    expect((wrapper.vm.$ as any).setupState.form.selectValue).toBe('old/old-model')
    wrapper.unmount()
  })

  it('restores the saved model state and submit gate after a later selection fails', async () => {
    const wrapper = mount(ModelConfig, {
      props: { model_config: { provider: 'old', model: 'old-model', parameters: { temperature: 0.9 } } },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    await flushPromises()
    mocks.loadLanguageModel.mockImplementation(async (_provider: string, model: string) => {
      if (model === 'model-b') {
        mocks.languageModel.value = { parameters: [{ name: 'max_tokens', default: 40 }] }
      } else if (model === 'model-c') {
        throw new Error('model C unavailable')
      } else {
        mocks.languageModel.value = { parameters: [{ name: 'temperature', default: 0.1 }] }
      }
      return true
    })

    const select = wrapper.findComponent(SelectStub)
    const trigger = wrapper.findComponent(TriggerStub)
    const state = (wrapper.vm.$ as any).setupState
    select.vm.$emit('update:modelValue', 'provider-b/model-b')
    select.vm.$emit('change', 'provider-b/model-b')
    await flushPromises()
    expect(state.form.parameters).toEqual({ max_tokens: 40 })

    select.vm.$emit('update:modelValue', 'provider-c/model-c')
    select.vm.$emit('change', 'provider-c/model-c')
    trigger.vm.$emit('hide')
    await flushPromises()

    expect(state.form.selectValue).toBe('old/old-model')
    expect(state.form.parameters).toEqual({ temperature: 0.9 })
    expect(state.language_model.parameters).toEqual([{ name: 'temperature', default: 0.1 }])
    expect(wrapper.emitted('update:model_config')).toBeUndefined()

    trigger.vm.$emit('hide')
    await flushPromises()
    expect(wrapper.emitted('update:model_config')).toEqual([[{
      provider: 'old', model: 'old-model', parameters: { temperature: 0.9 },
    }]])
    wrapper.unmount()
  })

  it('reports failure loading the configured model details', async () => {
    mocks.loadLanguageModel.mockRejectedValueOnce(new Error('configured model unavailable'))
    const wrapper = mount(ModelConfig, {
      props: { model_config: { provider: 'old', model: 'old-model', parameters: {} } },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    await flushPromises()

    expect(mocks.messageError).toHaveBeenCalledWith('configured model unavailable')
    wrapper.unmount()
  })

  it('ignores a stale model detail failure after a newer selection succeeds', async () => {
    const olderRequest = deferred()
    const wrapper = mount(ModelConfig, {
      props: { model_config: { provider: 'old', model: 'old-model', parameters: {} } },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    await flushPromises()
    mocks.loadLanguageModel.mockImplementation((_provider: string, model: string) => {
      return model === 'first-model' ? olderRequest.promise : Promise.resolve(true)
    })

    const select = wrapper.findComponent(SelectStub)
    const trigger = wrapper.findComponent(TriggerStub)
    select.vm.$emit('update:modelValue', 'first/first-model')
    select.vm.$emit('change', 'first/first-model')
    select.vm.$emit('update:modelValue', 'second/second-model')
    select.vm.$emit('change', 'second/second-model')
    await flushPromises()
    trigger.vm.$emit('hide')
    await flushPromises()
    olderRequest.reject(new Error('stale model request failed'))
    await flushPromises()

    expect(mocks.messageError).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:model_config')).toEqual([[{
      provider: 'second', model: 'second-model', parameters: { temperature: 0.2 },
    }]])
    wrapper.unmount()
  })

  it('reports a model list load failure', async () => {
    mocks.loadLanguageModels.mockRejectedValueOnce(new Error('model list unavailable'))
    const wrapper = mount(ModelConfig, {
      props: { model_config: {} },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    await flushPromises()

    expect(mocks.messageError).toHaveBeenCalledWith('model list unavailable')
    wrapper.unmount()
  })
})
