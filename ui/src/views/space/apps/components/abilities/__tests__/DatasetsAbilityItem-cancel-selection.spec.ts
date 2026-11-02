import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { expect, it, vi } from 'vitest'
import DatasetsAbilityItem from '../DatasetsAbilityItem.vue'

const mocks = vi.hoisted(() => ({ load: vi.fn(), update: vi.fn(), datasets: null as any }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', () => ({ useUpdateDraftAppConfig: () => ({ loading: ref(false), handleUpdateDraftAppConfig: mocks.update }) }))
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
const ButtonStub = defineComponent({ emits: ['click'], template: '<button @click="$emit(\'click\', $event)"><slot /></button>' })
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
