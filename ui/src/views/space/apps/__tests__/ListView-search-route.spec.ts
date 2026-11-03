import { flushPromises, shallowMount } from '@vue/test-utils'
import { reactive, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import AppListView from '@/views/space/apps/ListView.vue'

const mocks = vi.hoisted(() => ({ route: null as any, loadApps: vi.fn() }))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mocks.route,
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  }
})
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/stores/account', () => ({ useAccountStore: () => ({ account: { name: 'Owner' } }) }))
vi.mock('@/utils/helper', () => ({ getUserAvatarUrl: () => '' }))
vi.mock('@/views/space/apps/components/CreateOrUpdateAppModal.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/hooks/use-app', () => ({
  useCopyApp: () => ({ handleCopyApp: vi.fn() }),
  useDeleteApp: () => ({ handleDeleteApp: vi.fn() }),
  useGetAppsWithPage: () => ({
    loading: ref(false),
    apps: ref([]),
    paginator: ref({ current_page: 1, total_page: 1 }),
    loadApps: mocks.loadApps,
  }),
}))

describe('app list search route', () => {
  it('uses an empty search when route navigation removes the query', async () => {
    mocks.route = reactive({ path: '/space/apps', query: { search_word: 'northwind' } })
    mocks.loadApps.mockReset()
    const wrapper = shallowMount(AppListView)
    await flushPromises()

    mocks.loadApps.mockClear()
    mocks.route.query = {}
    await flushPromises()

    expect(mocks.loadApps).toHaveBeenCalledWith(true, '')
    wrapper.unmount()
  })
})
