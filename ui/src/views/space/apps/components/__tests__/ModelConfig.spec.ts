import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'
import ModelConfig from '../ModelConfig.vue'

const mocks = vi.hoisted(() => ({
  languageModel: null as any,
  loadLanguageModel: vi.fn(),
  loadModels: vi.fn(),
  updateDraft: vi.fn().mockResolvedValue(undefined),
  messageError: vi.fn(),
}))

vi.mock('@/hooks/use-language-model', () => ({
  useGetLanguageModel: () => ({ loading: ref(false), language_model: mocks.languageModel, loadLanguageModel: mocks.loadLanguageModel }),
  useGetLanguageModels: () => ({ language_models: ref([]), loadLanguageModels: mocks.loadModels }),
}))
vi.mock('@/hooks/use-app', () => ({ useUpdateDraftAppConfig: () => ({ handleUpdateDraftAppConfig: mocks.updateDraft }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.messageError } }))

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
    mocks.loadModels.mockReset().mockResolvedValue(undefined)
    mocks.languageModel = ref({ parameters: [] })
    mocks.loadLanguageModel.mockImplementation(async (_provider: string, model: string) => {
      if (model === 'new-model') await pendingLoad.promise
      mocks.languageModel.value = { parameters: [{ name: 'temperature', default: 0.2 }] }
      return true
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

  it('ignores a prior save after a newer model selection completes', async () => {
    const firstSave = deferred()
    mocks.updateDraft.mockReturnValueOnce(firstSave.promise).mockResolvedValueOnce(undefined)
    const wrapper = mount(ModelConfig, {
      props: { app_id: 'app-1', model_config: { provider: 'old', model: 'old-model', parameters: { temperature: 0.9 } }, dialog_round: 3 },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    await flushPromises()
    const select = wrapper.findComponent(SelectStub)
    const trigger = wrapper.findComponent(TriggerStub)

    select.vm.$emit('update:modelValue', 'first/first-model')
    select.vm.$emit('change', 'first/first-model')
    trigger.vm.$emit('hide')
    await flushPromises()
    select.vm.$emit('update:modelValue', 'second/second-model')
    select.vm.$emit('change', 'second/second-model')
    trigger.vm.$emit('hide')
    await flushPromises()
    firstSave.resolve()
    await flushPromises()

    expect(wrapper.emitted('update:model_config')).toEqual([[{
      provider: 'second',
      model: 'second-model',
      parameters: { temperature: 0.2 },
    }]])
    wrapper.unmount()
  })

  it('keeps the previous model when selected defaults fail to load', async () => {
    const wrapper = mount(ModelConfig, {
      props: { app_id: 'app-1', model_config: { provider: 'old', model: 'old-model', parameters: { temperature: 0.9 } }, dialog_round: 3 },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    await flushPromises()
    mocks.loadLanguageModel.mockRejectedValueOnce(new Error('model details unavailable'))
    mocks.messageError.mockReset()
    const select = wrapper.findComponent(SelectStub)
    select.vm.$emit('update:modelValue', 'broken/broken-model')
    select.vm.$emit('change', 'broken/broken-model')
    wrapper.findComponent(TriggerStub).vm.$emit('hide')
    await flushPromises()

    const state = (wrapper.vm.$ as any).setupState
    expect(state.form.selectValue).toBe('old/old-model')
    expect(mocks.updateDraft).not.toHaveBeenCalled()
    expect(mocks.messageError).toHaveBeenCalledWith('model details unavailable')
    wrapper.unmount()
  })

  it('reports model list failures only while the editor is mounted', async () => {
    mocks.loadModels.mockRejectedValueOnce(new Error('model list unavailable'))
    const wrapper = mount(ModelConfig, {
      props: { app_id: 'app-1', model_config: {}, dialog_round: 3 },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    await flushPromises()
    expect(mocks.messageError).toHaveBeenCalledWith('model list unavailable')
    wrapper.unmount()

    let rejectLoad!: (error: Error) => void
    mocks.loadModels.mockReset().mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectLoad = reject }))
    const unmountedWrapper = mount(ModelConfig, {
      props: { app_id: 'app-1', model_config: {}, dialog_round: 3 },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    unmountedWrapper.unmount()
    mocks.messageError.mockReset()
    rejectLoad(new Error('late model list failure'))
    await flushPromises()
    expect(mocks.messageError).not.toHaveBeenCalled()
  })

  it('reports only the current configured-model detail failure', async () => {
    const requests: { reject: (error: Error) => void }[] = []
    mocks.loadModels.mockReset().mockResolvedValue(undefined)
    mocks.loadLanguageModel.mockReset().mockImplementation(() => new Promise((_resolve, reject) => requests.push({ reject })))
    mocks.messageError.mockReset()
    const wrapper = mount(ModelConfig, {
      props: { app_id: 'app-1', model_config: { provider: 'old', model: 'old-model' }, dialog_round: 3 },
      global: { stubs: { 'a-trigger': TriggerStub, 'a-select': SelectStub } },
    })
    await wrapper.setProps({ model_config: { provider: 'new', model: 'new-model' } })
    requests[0].reject(new Error('stale model details unavailable'))
    await flushPromises()
    expect(mocks.messageError).not.toHaveBeenCalled()
    requests[1].reject(new Error('current model details unavailable'))
    await flushPromises()
    expect(mocks.messageError).toHaveBeenCalledWith('current model details unavailable')

    mocks.messageError.mockReset()
    await wrapper.setProps({ model_config: { provider: 'late', model: 'late-model' } })
    wrapper.unmount()
    requests[2].reject(new Error('late model details unavailable'))
    await flushPromises()
    expect(mocks.messageError).not.toHaveBeenCalled()
  })
})
