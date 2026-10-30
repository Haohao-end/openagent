import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockMessage, mockGetPublicApps, mockGetAppTags, mockForkPublicApp, mockRouterPush } = vi.hoisted(() => ({
  mockMessage: { error: vi.fn(), success: vi.fn() },
  mockGetPublicApps: vi.fn(),
  mockGetAppTags: vi.fn(),
  mockForkPublicApp: vi.fn(),
  mockRouterPush: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: mockRouterPush }) }))
vi.mock('@arco-design/web-vue', () => ({ Message: mockMessage }))
vi.mock('@/services/public-app', () => ({
  getPublicApps: mockGetPublicApps,
  getAppTags: mockGetAppTags,
  forkPublicApp: mockForkPublicApp,
}))

const SearchStub = defineComponent({
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue', 'search'],
  setup(props, { emit }) {
    return () =>
      h('div', [
        h('input', {
          'data-testid': 'public-app-search',
          value: props.modelValue,
          onInput: (event: Event) => emit('update:modelValue', (event.target as HTMLInputElement).value),
        }),
        h('button', { 'data-testid': 'public-app-search-submit', onClick: () => emit('search') }),
      ])
  },
})

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const appsResponse = (id: string, name: string, totalPage = 1) => ({
  data: {
    list: [{ id, name, icon: '', description: '', tags: [] }],
    paginator: { total_page: totalPage },
  },
})

describe('PublicAppsListView request ordering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetAppTags.mockResolvedValue({ data: { tags: [] } })
  })

  it('runs the latest search and ignores the stale list response', async () => {
    const requestOld = deferred<ReturnType<typeof appsResponse>>()
    const requestNew = deferred<ReturnType<typeof appsResponse>>()
    mockGetPublicApps.mockReturnValueOnce(requestOld.promise).mockReturnValueOnce(requestNew.promise)

    const { default: ListView } = await import('../ListView.vue')
    const wrapper = mount(ListView, {
      global: { stubs: { 'a-input-search': SearchStub } },
    })
    await flushPromises()

    await wrapper.get('[data-testid="public-app-search"]').setValue('new query')
    await wrapper.get('[data-testid="public-app-search-submit"]').trigger('click')
    await nextTick()

    expect(mockGetPublicApps).toHaveBeenCalledTimes(2)
    expect(mockGetPublicApps.mock.calls[1][0].search_word).toBe('new query')

    requestNew.resolve(appsResponse('new-app', 'New App'))
    await flushPromises()
    requestOld.resolve(appsResponse('old-app', 'Old App'))
    await flushPromises()

    expect(wrapper.text()).toContain('New App')
    expect(wrapper.text()).not.toContain('Old App')
    wrapper.unmount()
  })

  it('retries the same page after an infinite-scroll request fails', async () => {
    mockGetPublicApps
      .mockResolvedValueOnce(appsResponse('app-1', 'Page 1', 2))
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce(appsResponse('app-2', 'Page 2', 2))
    const { default: ListView } = await import('../ListView.vue')
    const wrapper = mount(ListView)
    await flushPromises()

    const list = wrapper.find('.overflow-y-auto')
    await list.trigger('scroll')
    await flushPromises()
    await list.trigger('scroll')
    await flushPromises()

    expect(mockGetPublicApps.mock.calls.map(([params]) => params.current_page)).toEqual([1, 2, 2])
    expect(wrapper.text()).toContain('Page 2')
    wrapper.unmount()
  })

  it('ignores a list failure after the page unmounts', async () => {
    let rejectRequest!: (reason: Error) => void
    const request = new Promise<ReturnType<typeof appsResponse>>((_resolve, reject) => {
      rejectRequest = reject
    })
    mockGetPublicApps.mockReturnValue(request)
    const { default: ListView } = await import('../ListView.vue')
    const wrapper = mount(ListView)
    await flushPromises()
    wrapper.unmount()

    rejectRequest(new Error('late failure'))
    await flushPromises()

    expect(mockMessage.error).not.toHaveBeenCalled()
  })

  it('ignores a tag failure after the page unmounts', async () => {
    const request = deferred<{ data: { tags: { id: string; name: string }[] } }>()
    mockGetPublicApps.mockResolvedValue(appsResponse('app', 'App'))
    mockGetAppTags.mockReturnValueOnce(request.promise)
    const { default: ListView } = await import('../ListView.vue')
    const wrapper = mount(ListView)
    await flushPromises()
    wrapper.unmount()

    request.reject(new Error('late tags failure'))
    await flushPromises()
    expect(mockMessage.error).not.toHaveBeenCalled()
  })

  it('does not navigate after a fork completes after unmount', async () => {
    const request = deferred<{ data: { id: string; name: string } }>()
    mockGetPublicApps.mockResolvedValue(appsResponse('app', 'App'))
    mockForkPublicApp.mockReturnValueOnce(request.promise)
    const { default: ListView } = await import('../ListView.vue')
    const wrapper = mount(ListView)
    await flushPromises()
    await wrapper.find('.mt-3 button').trigger('click')
    wrapper.unmount()

    request.resolve({ data: { id: 'forked', name: 'Forked' } })
    await flushPromises()
    expect(mockMessage.success).not.toHaveBeenCalled()
    expect(mockRouterPush).not.toHaveBeenCalled()
  })
})
