import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ListView from '../ListView.vue'

const mocks = vi.hoisted(() => ({
  getMcpProvidersWithPage: vi.fn(),
  deleteMcpProvider: vi.fn(),
  publishMcpProvider: vi.fn(),
  unpublishMcpProvider: vi.fn(),
  route: null as { path: string; query: Record<string, string | undefined> } | null,
  router: { replace: vi.fn() },
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mocks.route,
    useRouter: () => mocks.router,
  }
})

vi.mock('@/services/mcp', () => ({
  getMcpProvidersWithPage: mocks.getMcpProvidersWithPage,
  deleteMcpProvider: mocks.deleteMcpProvider,
  publishMcpProvider: mocks.publishMcpProvider,
  unpublishMcpProvider: mocks.unpublishMcpProvider,
}))

vi.mock('@/stores/account', () => ({
  useAccountStore: () => ({ account: { avatar: '', name: 'Test User' } }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: 'en-US' } }),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: { error: vi.fn(), success: vi.fn() },
  Modal: { warning: vi.fn() },
}))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

const providerResponse = (label: string) => ({
  data: {
    list: [{
      id: label,
      label,
      name: label,
      description: 'provider description',
      icon: '',
      background: '#1677ff',
      category: 'utility',
      transport: 'streamable_http',
      is_bindable: true,
      bind_reason: '',
      creator_name: 'Creator',
      creator_avatar: '',
      updated_at: 1,
      created_at: 1,
    }],
    paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
  },
})

const passthrough = { template: '<div><slot /></div>' }

describe('space MCP provider list search ordering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    const route = reactive({ path: '/space/mcp', query: { search_word: '' } })
    mocks.route = route
  })

  it('runs a search started during loading and ignores the prior response', async () => {
    const oldRequest = deferred<ReturnType<typeof providerResponse>>()
    const newRequest = deferred<ReturnType<typeof providerResponse>>()
    mocks.getMcpProvidersWithPage
      .mockReturnValueOnce(oldRequest.promise)
      .mockReturnValueOnce(newRequest.promise)

    const wrapper = mount(ListView, {
      global: {
        stubs: {
          'a-spin': passthrough,
          'a-row': passthrough,
          'a-col': passthrough,
          'a-card': passthrough,
          'a-avatar': passthrough,
          'a-tag': passthrough,
          'a-dropdown': passthrough,
          'a-button': passthrough,
          'a-doption': passthrough,
          'a-empty': passthrough,
          'create-or-update-mcp-modal': passthrough,
          'icon-more': true,
        },
      },
    })

    expect(mocks.getMcpProvidersWithPage).toHaveBeenCalledTimes(1)
    const route = mocks.route
    if (!route) throw new Error('route mock was not initialized')
    route.query.search_word = 'new query'
    await flushPromises()
    const callsAfterSearch = mocks.getMcpProvidersWithPage.mock.calls.length

    newRequest.resolve(providerResponse('New Provider'))
    await flushPromises()
    oldRequest.resolve(providerResponse('Old Provider'))
    await flushPromises()

    expect(callsAfterSearch).toBe(2)
    expect(mocks.getMcpProvidersWithPage.mock.calls[1][0].search_word).toBe('new query')
    expect(wrapper.text()).toContain('New Provider')
    expect(wrapper.text()).not.toContain('Old Provider')
    wrapper.unmount()
  })
})
