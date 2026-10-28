import { defineComponent, h, onMounted } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import AppLayoutView from '../AppLayoutView.vue'

const state = vi.hoisted(() => ({ route: { params: { app_id: 'app-1' } }, childMounts: 0 }))

vi.mock('vue-router', () => ({ useRoute: () => state.route }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  return {
    useGetApp: () => ({ loading: ref(false), app: ref({ id: 'app-1', name: 'App', status: 'draft' }), loadApp: vi.fn() }),
    usePublish: () => ({ loading: ref(false), handlePublish: vi.fn() }),
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
})
