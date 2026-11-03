import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { expect, it, vi } from 'vitest'
import DatasetsAbilityItem from '../DatasetsAbilityItem.vue'

const mocks = vi.hoisted(() => ({ load: vi.fn(), update: vi.fn(), datasets: null as any }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  const loading = ref(false)
  return { useUpdateDraftAppConfig: () => ({ loading, handleUpdateDraftAppConfig: async (...args: any[]) => {
    loading.value = true
    try { return await mocks.update(...args) } finally { loading.value = false }
  } }) }
})
vi.mock('@/hooks/use-dataset', async () => {
  const { ref } = await import('vue')
  return { useGetDatasetsWithPage: () => {
    const datasets = ref([{ id: 'ds-1', name: 'Available dataset', icon: '', description: '' }])
    mocks.datasets = datasets
    return { loading: ref(false), paginator: ref({ current_page: 1, total_page: 1 }), datasets, loadDatasets: mocks.load }
  } }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { warning: vi.fn() } }))

const WrapperStub = { template: '<div><slot /><slot name="header" /><slot name="extra" /></div>' }
const ButtonStub = defineComponent({ props: ['disabled'], emits: ['click'], template: '<button :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>' })
const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible"><slot /></div>' })

it('does not retain an unsaved dataset after cancelling a later selection', async () => {
  mocks.load.mockImplementation(async () => { mocks.datasets.value = [{ id: 'ds-1', name: 'Available dataset', icon: '', description: '' }] })
  const wrapper = mount(DatasetsAbilityItem, {
    props: { app_id: 'app-1', datasets: [], retrieval_config: { retrieval_strategy: 'semantic', k: 4, score: 0 } },
    global: { stubs: { 'a-collapse-item': WrapperStub, 'a-button': ButtonStub, 'a-modal': ModalStub, 'a-space': WrapperStub, 'a-spin': WrapperStub, 'a-avatar': WrapperStub, 'a-empty': WrapperStub, 'a-row': WrapperStub, 'a-col': WrapperStub, 'a-form': WrapperStub, 'a-form-item': WrapperStub, 'a-radio-group': WrapperStub, 'a-radio': WrapperStub, 'a-slider': WrapperStub, 'a-input-number': WrapperStub, 'icon-plus': true, 'icon-delete': true, 'icon-close': true, 'icon-language': true } },
  })
  await flushPromises()
  const open = () => wrapper.findAll('button')[1].trigger('click')
  const cancel = () => wrapper.findAll('button').find(button => button.text() === 'common.actions.cancel')!.trigger('click')
  await open()
  await flushPromises()
  await cancel()
  await open()
  await flushPromises()
  const row = wrapper.findAll('.cursor-pointer').find(item => item.text().includes('Available dataset'))!
  await row.trigger('click')
  await cancel()
  await open()
  await flushPromises()
  const reopenedRow = wrapper.findAll('.cursor-pointer').find(item => item.text().includes('Available dataset'))!
  expect(reopenedRow.classes()).not.toContain('bg-blue-50')
  wrapper.unmount()
})

it('clears the picker baseline when the last bound dataset is removed', async () => {
  const wrapper = mount(DatasetsAbilityItem, {
    props: { app_id: 'app-1', datasets: [{ id: 'ds-1', name: 'Bound dataset', icon: '', description: '' }], retrieval_config: { retrieval_strategy: 'semantic', k: 4, score: 0 } },
    global: { stubs: { 'a-collapse-item': WrapperStub, 'a-button': ButtonStub, 'a-modal': ModalStub, 'a-space': WrapperStub, 'a-spin': WrapperStub, 'a-avatar': WrapperStub, 'a-empty': WrapperStub, 'a-row': WrapperStub, 'a-col': WrapperStub, 'a-form': WrapperStub, 'a-form-item': WrapperStub, 'a-radio-group': WrapperStub, 'a-radio': WrapperStub, 'a-slider': WrapperStub, 'a-input-number': WrapperStub, 'icon-plus': true, 'icon-delete': true, 'icon-close': true, 'icon-language': true } },
  })
  await flushPromises()
  const remove = wrapper.findAll('button').find(button => button.classes().includes('!text-red-700'))!
  await remove.trigger('click')
  await wrapper.setProps({ datasets: [] })
  const state = (wrapper.vm.$ as any).setupState

  expect(state.activateDatasets).toEqual([])
  expect(state.originDatasets).toEqual([])
  wrapper.unmount()
})

it('keeps the dataset picker open while a submitted selection is saving', async () => {
  let resolveUpdate!: () => void
  const pending = new Promise<void>((resolve) => { resolveUpdate = resolve })
  mocks.update.mockReset().mockReturnValue(pending)
  const wrapper = mount(DatasetsAbilityItem, {
    props: { app_id: 'app-1', datasets: [], retrieval_config: { retrieval_strategy: 'semantic', k: 4, score: 0 } },
    global: { stubs: { 'a-collapse-item': WrapperStub, 'a-button': ButtonStub, 'a-modal': ModalStub, 'a-space': WrapperStub, 'a-spin': WrapperStub, 'a-avatar': WrapperStub, 'a-empty': WrapperStub, 'a-row': WrapperStub, 'a-col': WrapperStub, 'a-form': WrapperStub, 'a-form-item': WrapperStub, 'a-radio-group': WrapperStub, 'a-radio': WrapperStub, 'a-slider': WrapperStub, 'a-input-number': WrapperStub, 'icon-plus': true, 'icon-delete': true, 'icon-close': true, 'icon-language': true } },
  })
  await flushPromises()
  await wrapper.findAll('button')[1].trigger('click')
  await flushPromises()
  await wrapper.findAll('.cursor-pointer').find(item => item.text().includes('Available dataset'))!.trigger('click')

  const state = (wrapper.vm.$ as any).setupState
  const submit = state.handleSubmitDatasets()
  await nextTick()
  expect(mocks.update).toHaveBeenCalledWith('app-1', { datasets: ['ds-1'] })
  const cancel = wrapper.findAll('button').find(button => button.text() === 'common.actions.cancel')!
  expect(cancel.attributes('disabled')).toBeDefined()
  await cancel.trigger('click')
  expect(state.datasetsModalVisible).toBe(true)

  resolveUpdate()
  await submit
  expect(wrapper.emitted('update:datasets')?.[0][0]).toEqual([
    { id: 'ds-1', name: 'Available dataset', icon: '', description: '' },
  ])
  wrapper.unmount()
})

it('does not submit stale dataset lists for concurrent removals', async () => {
  const pending = new Promise<void>(() => {})
  mocks.update.mockReset().mockReturnValue(pending)
  const wrapper = mount(DatasetsAbilityItem, {
    props: { app_id: 'app-1', datasets: [
      { id: 'ds-1', name: 'First', icon: '', description: '' },
      { id: 'ds-2', name: 'Second', icon: '', description: '' },
    ], retrieval_config: { retrieval_strategy: 'semantic', k: 4, score: 0 } },
    global: { stubs: { 'a-collapse-item': WrapperStub, 'a-button': ButtonStub, 'a-modal': ModalStub, 'a-space': WrapperStub, 'a-spin': WrapperStub, 'a-avatar': WrapperStub, 'a-empty': WrapperStub, 'a-row': WrapperStub, 'a-col': WrapperStub, 'a-form': WrapperStub, 'a-form-item': WrapperStub, 'a-radio-group': WrapperStub, 'a-radio': WrapperStub, 'a-slider': WrapperStub, 'a-input-number': WrapperStub, 'icon-plus': true, 'icon-delete': true, 'icon-close': true, 'icon-language': true } },
  })
  await flushPromises()
  const removals = wrapper.findAll('button').filter((button) => button.classes().includes('!text-red-700'))

  await removals[0].trigger('click')
  await nextTick()
  await removals[1].trigger('click')

  expect(mocks.update).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})
