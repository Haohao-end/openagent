import { flushPromises, mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockMessage, mockGetPublicAppDetail, mockRoute } = vi.hoisted(() => ({
  mockMessage: { error: vi.fn(), success: vi.fn() },
  mockGetPublicAppDetail: vi.fn(),
  mockRoute: { params: { app_id: 'app-a' } },
}))
const mockReactiveRoute = reactive(mockRoute)

vi.mock('vue-router', () => ({
  useRoute: () => mockReactiveRoute,
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@arco-design/web-vue', () => ({ Message: mockMessage }))

vi.mock('@/services/public-app', () => ({
  getPublicAppDetail: mockGetPublicAppDetail,
  forkPublicApp: vi.fn(),
}))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

const appResponse = (id: string, name: string) => ({
  data: {
    id,
    name,
    icon: '',
    description: '',
    tags: [],
    creator_name: '',
    creator_avatar: '',
    published_at: 0,
    created_at: 0,
    updated_at: 0,
  },
})

describe('AppPreviewLayoutView request ordering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockReactiveRoute.params.app_id = 'app-a'
  })

  it('keeps the currently selected app when an older request resolves last', async () => {
    const requestA = deferred<ReturnType<typeof appResponse>>()
    const requestB = deferred<ReturnType<typeof appResponse>>()
    mockGetPublicAppDetail.mockReturnValueOnce(requestA.promise).mockReturnValueOnce(requestB.promise)

    const { default: AppPreviewLayoutView } = await import('../AppPreviewLayoutView.vue')
    const wrapper = mount(AppPreviewLayoutView, {
      global: {
        stubs: [
          'router-link',
          'router-view',
          'a-button',
          'a-skeleton-line',
          'a-tag',
          'icon-left',
          'icon-apps',
          'icon-user',
          'icon-plus',
        ],
      },
    })
    await flushPromises()

    mockReactiveRoute.params.app_id = 'app-b'
    await nextTick()
    expect(mockGetPublicAppDetail).toHaveBeenCalledTimes(2)

    requestB.resolve(appResponse('app-b', 'App B'))
    await flushPromises()
    requestA.resolve(appResponse('app-a', 'App A'))
    await flushPromises()

    expect(wrapper.text()).toContain('App B')
    expect(wrapper.text()).not.toContain('App A')
    wrapper.unmount()
  })
})
