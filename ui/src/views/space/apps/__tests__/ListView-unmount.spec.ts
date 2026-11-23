import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import ListView from '../ListView.vue'

const mocks = vi.hoisted(() => ({
  route: { query: { search_word: '', create_type: '' }, path: '/space/apps' },
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  messageError: vi.fn(),
  loadApps: vi.fn(),
  handleDeleteApp: vi.fn(),
  handleCopyApp: vi.fn(),
}))

const loading = ref(false)
const apps = ref<any[]>([])
const paginator = ref({ current_page: 1, page_size: 20, total_page: 1, total_record: 0 })

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: mocks.routerPush, replace: mocks.routerReplace }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: { error: mocks.messageError },
}))

vi.mock('@/stores/account', () => ({
  useAccountStore: () => ({ account: { name: 'Admin', avatar: '' } }),
}))

vi.mock('@/hooks/use-app', () => ({
  useGetAppsWithPage: () => ({
    loading,
    apps,
    paginator,
    loadApps: mocks.loadApps,
  }),
  useDeleteApp: () => ({
    handleDeleteApp: mocks.handleDeleteApp,
  }),
  useCopyApp: () => ({
    handleCopyApp: mocks.handleCopyApp,
  }),
}))

vi.mock('@/views/space/apps/components/CreateOrUpdateAppModal.vue', () => ({
  default: { name: 'CreateOrUpdateAppModal', template: '<div />' },
}))

vi.mock('@/components/skeletons/CardGridSkeleton.vue', () => ({
  default: { name: 'CardGridSkeleton', template: '<div />' },
}))

describe('App ListView unmounted safety', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    loading.value = false
    apps.value = []
    paginator.value = { current_page: 1, page_size: 20, total_page: 1, total_record: 0 }
    mocks.loadApps.mockResolvedValue(undefined)
  })

  it('loads apps on mount and reports error if still mounted', async () => {
    mocks.loadApps.mockRejectedValueOnce(new Error('Network error'))
    shallowMount(ListView)
    await flushPromises()

    expect(mocks.loadApps).toHaveBeenCalledWith(true, '')
    expect(mocks.messageError).toHaveBeenCalledWith('Network error')
  })

  it('suppresses load error notification after component is unmounted', async () => {
    let rejectLoad!: (reason: Error) => void
    mocks.loadApps.mockReturnValueOnce(
      new Promise((_resolve, reject) => {
        rejectLoad = reject
      }),
    )

    const wrapper = shallowMount(ListView)
    await flushPromises()

    wrapper.unmount()
    rejectLoad(new Error('Late network error'))
    await flushPromises()

    expect(mocks.messageError).not.toHaveBeenCalled()
  })

  it('ignores scroll events when component is unmounted', async () => {
    const wrapper = shallowMount(ListView)
    await flushPromises()
    mocks.loadApps.mockClear()

    wrapper.unmount()
    const setupState = (wrapper.vm.$ as any).setupState
    setupState.handleScroll({
      target: { scrollTop: 1000, clientHeight: 500, scrollHeight: 1500 },
    } as unknown as Event)

    expect(mocks.loadApps).not.toHaveBeenCalled()
  })
})
