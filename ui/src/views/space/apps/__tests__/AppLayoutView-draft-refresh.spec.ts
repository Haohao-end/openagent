import { defineComponent, h, onMounted } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import AppLayoutView from '../AppLayoutView.vue'

const state = vi.hoisted(() => ({
  route: { params: { app_id: 'app-1' } },
  childMounts: 0,
  loadApp: vi.fn(),
  loadedAppId: '',
  handlePublish: vi.fn(),
}))

vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  state.route = reactive(state.route)
  return { useRoute: () => state.route }
})
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  return {
    useGetApp: () => ({ loading: ref(false), app: ref({ id: 'app-1', name: 'App', status: 'draft' }), loadApp: state.loadApp }),
    usePublish: () => ({ loading: ref(false), handlePublish: state.handlePublish }),
    useCancelPublish: () => ({ handleCancelPublish: vi.fn() }),
    useShareAppToSquare: () => ({ loading: ref(false), handleShareAppToSquare: vi.fn() }),
    useUnshareAppFromSquare: () => ({ handleUnshareAppFromSquare: vi.fn() }),
  }
})

const ActiveView = defineComponent({ setup: () => { onMounted(() => state.childMounts++); return () => h('div') } })
const RouterViewStub = defineComponent({ setup: (_, { slots }) => () => slots.default?.({ Component: ActiveView }) })
const DrawerStub = defineComponent({
  emits: ['load-draft-app-config'],
  setup: (_, { emit }) => () => h('button', { 'data-testid': 'rollback', onClick: () => emit('load-draft-app-config') }),
})
const ButtonStub = defineComponent({ emits: ['click'], template: `<button @click="$emit('click')"><slot /></button>` })

it('refreshes the active view after rolling a history version back to draft', async () => {
  state.childMounts = 0
  const wrapper = mount(AppLayoutView, {
    global: { stubs: { 'router-view': RouterViewStub, 'publish-history-drawer': DrawerStub } },
  })
  await flushPromises()
  expect(state.childMounts).toBe(1)

  await wrapper.get('[data-testid="rollback"]').trigger('click')
  await flushPromises()

  expect(state.childMounts).toBe(2)
  wrapper.unmount()
})

it('does not reload the old app when a publish action completes after route change', async () => {
  state.route.params.app_id = 'app-1'
  state.loadedAppId = ''
  state.loadApp.mockImplementation(async (id: string) => { state.loadedAppId = id })
  let finishPublish!: () => void
  state.handlePublish.mockImplementationOnce(() => new Promise<void>(resolve => { finishPublish = resolve }))
  const wrapper = mount(AppLayoutView, {
    global: { stubs: { 'router-view': RouterViewStub, 'publish-history-drawer': DrawerStub, 'a-button': ButtonStub } },
  })
  await flushPromises()
  await wrapper.findAll('button').find(button => button.text().includes('publishUpdate'))!.trigger('click')
  expect(finishPublish).toBeDefined()

  state.route.params = { app_id: 'app-2' }
  await flushPromises()
  expect(state.loadApp.mock.calls).toEqual([['app-1'], ['app-2']])
  expect(state.loadedAppId).toBe('app-2')
  finishPublish()
  await flushPromises()

  expect(state.loadedAppId).toBe('app-2')
  wrapper.unmount()
})
