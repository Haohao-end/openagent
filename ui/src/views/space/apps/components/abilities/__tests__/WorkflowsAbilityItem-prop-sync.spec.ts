import { shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import WorkflowsAbilityItem from '../WorkflowsAbilityItem.vue'

const mocks = vi.hoisted(() => ({ load: vi.fn(), update: vi.fn() }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  return { useUpdateDraftAppConfig: () => ({ loading: ref(false), handleUpdateDraftAppConfig: mocks.update }) }
})
vi.mock('@/hooks/use-workflow', async () => {
  const { ref } = await import('vue')
  return { useGetWorkflowsWithPage: () => ({ loading: ref(false), paginator: ref({}), workflows: ref([]), loadWorkflows: mocks.load }) }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { warning: vi.fn() } }))

const defaultStubs = {
  'a-avatar': true,
  'a-button': true,
  'a-col': true,
  'a-collapse-item': true,
  'a-empty': true,
  'a-modal': true,
  'a-row': true,
  'a-space': true,
  'a-spin': true,
  'icon-close': true,
  'icon-delete': true,
  'icon-plus': true,
}

it('syncs workflows that arrive after the ability first renders', async () => {
  const wrapper = shallowMount(WorkflowsAbilityItem, {
    props: { app_id: 'app-1', workflows: [] },
    global: { stubs: defaultStubs },
  })
  const workflow = { id: 'wf-1', name: 'Loaded workflow', icon: '', description: '' }
  await wrapper.setProps({ workflows: [workflow] })
  expect((wrapper.vm.$ as any).setupState.activateWorkflows).toEqual([workflow])
  wrapper.unmount()
})
