import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { expect, it, vi } from 'vitest'
import DatasetsAbilityItem from '../DatasetsAbilityItem.vue'

const mocks = vi.hoisted(() => ({ load: vi.fn(), update: vi.fn(), error: vi.fn() }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', () => ({ useUpdateDraftAppConfig: () => ({ loading: ref(false), handleUpdateDraftAppConfig: mocks.update }) }))
vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return { useGetDatasetsWithPage: () => ({ loading: ref(false), paginator: ref({ current_page: 1, total_page: 0 }), datasets: ref([]), loadDatasets: mocks.load }) }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { warning: vi.fn(), error: mocks.error } }))

const WrapperStub = { template: '<div><slot /><slot name="header" /><slot name="extra" /></div>' }
const ButtonStub = defineComponent({ emits: ['click'], template: '<button @click="$emit(\'click\', $event)"><slot /></button>' })
const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible"><slot /></div>' })
const SliderStub = defineComponent({ props: ['modelValue'], emits: ['update:modelValue'], template: '<input :value="modelValue" />' })

it('reports dataset load failures and ignores late failures after unmount', async () => {
  let rejectLateLoad!: (error: Error) => void
  const lateLoad = new Promise<void>((_, reject) => { rejectLateLoad = reject })
  mocks.load.mockReset().mockRejectedValueOnce(new Error('network unavailable')).mockReturnValueOnce(lateLoad)
  mocks.error.mockReset()
  const wrapper = mount(DatasetsAbilityItem, {
    props: { app_id: 'app-1', datasets: [], retrieval_config: { retrieval_strategy: 'semantic', k: 4, score: 0 } },
    global: { config: { errorHandler: vi.fn() }, stubs: { 'a-collapse-item': WrapperStub } },
  })
  await flushPromises()

  expect(mocks.error).toHaveBeenCalledWith('network unavailable')
  const state = (wrapper.vm.$ as any).setupState
  state.datasetsModalVisible = true
  await flushPromises()
  wrapper.unmount()
  rejectLateLoad(new Error('late failure'))
  await flushPromises()
  expect(mocks.error).toHaveBeenCalledTimes(1)
})

it('restores the saved retrieval settings after a later cancelled edit', async () => {
  const wrapper = mount(DatasetsAbilityItem, {
    props: { app_id: 'app-1', datasets: [], retrieval_config: { retrieval_strategy: 'semantic', k: 4, score: 0 } },
    global: { stubs: { 'a-collapse-item': WrapperStub, 'a-button': ButtonStub, 'a-modal': ModalStub, 'a-space': WrapperStub, 'a-spin': WrapperStub, 'a-avatar': WrapperStub, 'a-empty': WrapperStub, 'a-row': WrapperStub, 'a-col': WrapperStub, 'a-form': WrapperStub, 'a-form-item': WrapperStub, 'a-radio-group': WrapperStub, 'a-radio': WrapperStub, 'a-slider': SliderStub, 'a-input-number': WrapperStub, 'icon-plus': true, 'icon-delete': true, 'icon-close': true, 'icon-language': true } },
  })
  await flushPromises()
  const open = () => wrapper.findAll('button')[0].trigger('click')
  const cancel = () => wrapper.findAll('button').find(button => button.text() === 'common.actions.cancel')!.trigger('click')
  const change = async (value: number) => {
    wrapper.findAllComponents(SliderStub)[0].vm.$emit('update:modelValue', value)
    await flushPromises()
  }
  await open()
  await change(7)
  await cancel()
  await open()
  await change(9)
  await cancel()
  await open()
  expect(wrapper.findAllComponents(SliderStub)[0].props('modelValue')).toBe(4)
  wrapper.unmount()
})

it('keeps reopened retrieval settings open after an earlier save completes', async () => {
  let resolve!: () => void
  mocks.update.mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
  const wrapper = mount(DatasetsAbilityItem, { props: { app_id: 'app-1', datasets: [], retrieval_config: { retrieval_strategy: 'semantic', k: 4, score: 0 } }, global: { stubs: { 'a-collapse-item': WrapperStub, 'a-button': ButtonStub, 'a-modal': ModalStub, 'a-space': WrapperStub, 'a-spin': WrapperStub, 'a-avatar': WrapperStub, 'a-empty': WrapperStub, 'a-row': WrapperStub, 'a-col': WrapperStub, 'a-form': WrapperStub, 'a-form-item': WrapperStub, 'a-radio-group': WrapperStub, 'a-radio': WrapperStub, 'a-slider': SliderStub, 'a-input-number': WrapperStub, 'icon-plus': true, 'icon-delete': true, 'icon-close': true, 'icon-language': true } } })
  const state = (wrapper.vm.$ as any).setupState
  state.retrievalConfigModalVisible = true
  state.retrievalConfigForm.k = 6
  const save = state.handleSubmitRetrievalConfig()
  state.handleCancelRetrievalConfigModal()
  state.retrievalConfigModalVisible = true
  state.retrievalConfigForm.k = 8
  resolve()
  await save
  expect(state.retrievalConfigModalVisible).toBe(true)
  expect(state.retrievalConfigForm.k).toBe(8)
  wrapper.unmount()
})
