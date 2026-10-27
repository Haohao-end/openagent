import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockMessage, mockGetPublicApps, mockGetAppTags } = vi.hoisted(() => ({
  mockMessage: { error: vi.fn(), success: vi.fn() },
  mockGetPublicApps: vi.fn(),
  mockGetAppTags: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@arco-design/web-vue', () => ({ Message: mockMessage }))
vi.mock('@/services/public-app', () => ({
  getPublicApps: mockGetPublicApps,
  getAppTags: mockGetAppTags,
  forkPublicApp: vi.fn(),
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
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

const appsResponse = (id: string, name: string) => ({
  data: {
    list: [{ id, name, icon: '', description: '', tags: [] }],
    paginator: { total_page: 1 },
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
})
