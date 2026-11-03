import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { expect, it, vi } from 'vitest'
import WorkflowsAbilityItem from '../WorkflowsAbilityItem.vue'

const mocks = vi.hoisted(() => ({ load: vi.fn(), update: vi.fn(), workflows: null as any }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', () => ({ useUpdateDraftAppConfig: () => ({ loading: ref(false), handleUpdateDraftAppConfig: mocks.update }) }))
vi.mock('@/hooks/use-workflow', async () => {
  const { ref } = await import('vue')
  return { useGetWorkflowsWithPage: () => {
    const workflows = ref([{ id: 'wf-1', name: 'Available workflow', icon: '', description: '' }])
    mocks.workflows = workflows
    return { loading: ref(false), paginator: ref({ current_page: 1, total_page: 1 }), workflows, loadWorkflows: mocks.load }
  } }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { warning: vi.fn() } }))

const WrapperStub = { template: '<div><slot /><slot name="header" /><slot name="extra" /></div>' }
const ButtonStub = defineComponent({ emits: ['click'], template: '<button @click="$emit(\'click\', $event)"><slot /></button>' })
const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible"><slot /></div>' })

it('does not retain an unsaved workflow after cancelling a later selection', async () => {
  mocks.load.mockImplementation(async () => { mocks.workflows.value = [{ id: 'wf-1', name: 'Available workflow', icon: '', description: '' }] })
  const wrapper = mount(WorkflowsAbilityItem, {
    props: { app_id: 'app-1', workflows: [] },
    global: { stubs: { 'a-collapse-item': WrapperStub, 'a-button': ButtonStub, 'a-modal': ModalStub, 'a-space': WrapperStub, 'a-spin': WrapperStub, 'a-avatar': WrapperStub, 'a-empty': WrapperStub, 'a-row': WrapperStub, 'a-col': WrapperStub, 'icon-plus': true, 'icon-delete': true, 'icon-close': true } },
  })
  await flushPromises()
  const open = () => wrapper.findAll('button')[0].trigger('click')
  const cancel = () => wrapper.findAll('button').find(button => button.text() === 'common.actions.cancel')!.trigger('click')
  await open()
  await flushPromises()
  await cancel()
  await open()
  await flushPromises()
  const row = wrapper.findAll('.cursor-pointer').find(item => item.text().includes('Available workflow'))!
  await row.trigger('click')
  await cancel()
  await open()
  await flushPromises()
  const reopenedRow = wrapper.findAll('.cursor-pointer').find(item => item.text().includes('Available workflow'))!
  expect(reopenedRow.classes()).not.toContain('bg-blue-50')
  wrapper.unmount()
})

it('clears the picker baseline when the last bound workflow is removed', async () => {
  const wrapper = mount(WorkflowsAbilityItem, {
    props: { app_id: 'app-1', workflows: [{ id: 'wf-1', name: 'Bound workflow', icon: '', description: '' }] },
    global: { stubs: { 'a-collapse-item': WrapperStub, 'a-button': ButtonStub, 'a-modal': ModalStub, 'a-space': WrapperStub, 'a-spin': WrapperStub, 'a-avatar': WrapperStub, 'a-empty': WrapperStub, 'a-row': WrapperStub, 'a-col': WrapperStub, 'icon-plus': true, 'icon-delete': true, 'icon-close': true } },
  })
  await flushPromises()
  const remove = wrapper.findAll('button').find(button => button.classes().includes('!text-red-700'))!
  await remove.trigger('click')
  await wrapper.setProps({ workflows: [] })
  const state = (wrapper.vm.$ as any).setupState

  expect(state.activateWorkflows).toEqual([])
  expect(state.originWorkflows).toEqual([])
  wrapper.unmount()
})
