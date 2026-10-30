import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import McpListView from '@/views/store/mcp/ListView.vue'

const mocks = vi.hoisted(() => ({
  getPublicMcpCategories: vi.fn(),
  getPublicMcpProvidersWithPage: vi.fn(),
  getPublicMcpProvider: vi.fn(),
  messageError: vi.fn(),
}))

vi.mock('@/services/mcp', () => ({
  getPublicMcpCategories: mocks.getPublicMcpCategories,
  getPublicMcpProvidersWithPage: mocks.getPublicMcpProvidersWithPage,
  getPublicMcpProvider: mocks.getPublicMcpProvider,
}))

vi.mock('@arco-design/web-vue', async () => {
  const actual = await vi.importActual<typeof import('@arco-design/web-vue')>('@arco-design/web-vue')
  return { ...actual, Message: { ...actual.Message, error: mocks.messageError } }
})

vi.mock('@/views/space/mcp/components/CreateOrUpdateMcpModal.vue', () => ({
  default: defineComponent({
    name: 'CreateOrUpdateMcpModal',
    props: {
      visible: {
        type: Boolean,
        default: false,
      },
      callback: {
        type: Function,
        default: undefined,
      },
      mcp_provider_id: {
        type: String,
        default: '',
      },
    },
    template: '<div data-testid="create-mcp-modal" :data-visible="String(visible)"></div>',
  }),
}))

const buttonStub = defineComponent({
  name: 'ArcoButtonStub',
  emits: ['click'],
  template: '<button type="button" v-bind="$attrs" @click="$emit(\'click\', $event)"><slot /></button>',
})

const cardStub = defineComponent({
  emits: ['click'],
  template: '<div @click="$emit(\'click\')"><slot /></div>',
})

const drawerStub = defineComponent({
  props: ['visible'],
  emits: ['cancel'],
  template:
    '<section v-if="visible" data-testid="detail-drawer"><button data-testid="close-detail" @click="$emit(\'cancel\')" /><slot /></section>',
})

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((yes, no) => ((resolve = yes), (reject = no)))
  return { promise, resolve, reject }
}

const provider = (key: string) => ({
  provider_key: key,
  name: key,
  label: key,
  category: 'general',
  created_at: 1,
  tools: [],
})

const globalStubs = {
  'a-spin': {
    template: '<div><slot /></div>',
  },
  'a-avatar': {
    template: '<div><slot /></div>',
  },
  'a-button': buttonStub,
  'a-tag': {
    template: '<span><slot /></span>',
  },
  'a-card': cardStub,
  'a-col': {
    template: '<div><slot /></div>',
  },
  'a-empty': {
    template: '<div><slot /></div>',
  },
  'a-row': {
    template: '<div><slot /></div>',
  },
  'a-drawer': drawerStub,
  'a-input-search': {
    template: '<input />',
  },
  'card-grid-skeleton': {
    template: '<div />',
  },
  'resource-card-description': {
    template: '<div />',
  },
  'icon-computer': {
    template: '<span data-icon="computer" />',
  },
  'icon-close': {
    template: '<span />',
  },
  'icon-more': {
    template: '<span />',
  },
}

describe('store mcp list', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mocks.getPublicMcpCategories.mockResolvedValue({
      data: {
        categories: [
          { id: 'general', name: '通用', priority: 1, background: '#DBEAFE' },
          { id: 'coding', name: '编程工具', priority: 3, background: '#E0E7FF' },
          { id: 'content_creation', name: '内容创作', priority: 4, background: '#FEE2E2' },
          { id: 'media', name: '媒体音视频', priority: 5, background: '#FCE7F3' },
          { id: 'productivity', name: '效率工具', priority: 2, background: '#DCFCE7' },
          { id: 'data_analysis', name: '数据分析', priority: 6, background: '#EDE9FE' },
          { id: 'observability', name: '可观测运维', priority: 7, background: '#FEF3C7' },
          { id: 'other', name: '其他', priority: 99, background: '#E5E7EB' },
        ],
      },
    })

    mocks.getPublicMcpProvidersWithPage.mockResolvedValue({
      data: {
        list: [
          {
            provider_key: 'weather-mcp',
            name: 'weather-mcp',
            label: '天气 MCP',
            icon: '',
            background: '#DBEAFE',
            description: '查询实时天气和预报',
            category: 'general',
            transport: 'streamable_http',
            url: 'https://example.com/mcp',
            command: '',
            headers: [],
            tool_names: [],
            args: [],
            env: {},
            timeout_seconds: 30,
            source_type: 'catalog',
            source_key: 'weather',
            source_url: 'https://example.com/weather',
            creator_name: 'OpenAI',
            creator_avatar: '',
            is_public: true,
            is_bindable: true,
            bind_reason: '',
            published_at: 1700000000,
            created_at: 1700000000,
            updated_at: 1700000000,
            tool_count: 2,
            tools: [],
            binding: {},
          },
        ],
        paginator: {
          current_page: 1,
          page_size: 50,
          total_page: 1,
          total_record: 1,
        },
      },
    })

    mocks.getPublicMcpProvider.mockResolvedValue({
      data: {
        provider_key: 'weather-mcp',
        name: 'weather-mcp',
        label: '天气 MCP',
        icon: '',
        background: '#DBEAFE',
        description: '查询实时天气和预报',
        category: 'general',
        transport: 'streamable_http',
        url: 'https://example.com/mcp',
        command: '',
        headers: [],
        tool_names: [],
        args: [],
        env: {},
        timeout_seconds: 30,
        source_type: 'catalog',
        source_key: 'weather',
        source_url: 'https://example.com/weather',
        creator_name: 'OpenAI',
        creator_avatar: '',
        is_public: true,
        is_bindable: true,
        bind_reason: '',
        published_at: 1700000000,
        created_at: 1700000000,
        updated_at: 1700000000,
        tool_count: 2,
        tools: [],
        binding: {},
      },
    })
  })

  it('opens the local create modal and keeps the store page subtitle removed', async () => {
    const wrapper = shallowMount(McpListView, {
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()

    expect(mocks.getPublicMcpCategories).toHaveBeenCalledTimes(1)
    expect(mocks.getPublicMcpProvidersWithPage).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('MCP 广场')
    expect(wrapper.text()).not.toContain('公开免费 MCP 目录')
    expect(wrapper.text()).not.toContain('general')
    expect(wrapper.text()).not.toContain('仅查看')
    expect(wrapper.text()).not.toContain('天气 MCP 草稿')
    expect(wrapper.text()).not.toContain('当前环境不支持该 MCP')
    expect(wrapper.find('[data-icon="computer"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('全部')
    expect(wrapper.html()).toContain('rounded-lg !text-gray-700 px-3')
    expect(wrapper.html()).not.toContain('mcp-category-btn')

    ;['通用', '编程工具', '内容创作', '媒体音视频', '效率工具', '数据分析', '可观测运维', '其他'].forEach((category) => {
      expect(wrapper.text()).toContain(category)
    })

    const modal = wrapper.get('create-or-update-mcp-modal-stub')
    expect(modal.attributes('visible')).toBe('false')

    await wrapper.get('[data-testid="store-mcp-create-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('create-or-update-mcp-modal-stub').attributes('visible')).toBe('true')
  })

  it('ignores stale provider detail success and failure after switching providers', async () => {
    const requests = Array.from({ length: 4 }, () => deferred<{ data: ReturnType<typeof provider> }>())
    mocks.getPublicMcpProvider.mockImplementation(() => requests.shift()!.promise as never)
    mocks.getPublicMcpProvidersWithPage.mockResolvedValueOnce({ data: { list: [provider('provider-a'), provider('provider-b')] } } as never)
    const wrapper = shallowMount(McpListView, { global: { stubs: globalStubs } })
    const issues: string[] = []
    await flushPromises()
    const [providerA, providerB] = wrapper.findAllComponents(cardStub)
    const closeDetail = () => wrapper.get('[data-testid="close-detail"]').trigger('click')

    for (const [index, [stale, latest]] of [[requests[0], requests[1]], [requests[2], requests[3]]].entries()) {
      await providerA.trigger('click')
      await closeDetail()
      await providerB.trigger('click')
      latest.resolve({ data: provider('provider-b') })
      await flushPromises()
      index ? stale.reject(new Error('stale failure')) : stale.resolve({ data: provider('provider-a') })
      await flushPromises()
      const drawer = wrapper.find('[data-testid="detail-drawer"]')
      if (!drawer.exists() || !drawer.text().includes('provider-b')) issues.push(`stale ${index ? 'failure' : 'success'}`)
    }
    expect(issues).toEqual([])
    wrapper.unmount()
  })

  it('ignores detail success after the drawer closes', async () => {
    const pending = deferred<{ data: ReturnType<typeof provider> }>()
    mocks.getPublicMcpProvider.mockReturnValue(pending.promise as never)
    mocks.getPublicMcpProvidersWithPage.mockResolvedValueOnce({ data: { list: [provider('provider-a')] } } as never)
    const wrapper = shallowMount(McpListView, { global: { stubs: globalStubs } })
    await flushPromises()
    const setupState = (
      wrapper.vm.$ as unknown as { setupState: { activeProvider: ReturnType<typeof provider> | null } }
    ).setupState

    await wrapper.findComponent(cardStub).trigger('click')
    await wrapper.get('[data-testid="close-detail"]').trigger('click')
    pending.resolve({ data: provider('provider-a') })
    await flushPromises()

    expect(setupState.activeProvider).toBeNull()
    expect(wrapper.find('[data-testid="detail-drawer"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('does not show detail errors after the page unmounts', async () => {
    const pending = deferred<{ data: ReturnType<typeof provider> }>()
    mocks.getPublicMcpProvider.mockReturnValue(pending.promise as never)
    mocks.getPublicMcpProvidersWithPage.mockResolvedValueOnce({ data: { list: [provider('provider-a')] } } as never)
    const wrapper = shallowMount(McpListView, { global: { stubs: globalStubs } })
    await flushPromises()

    await wrapper.findComponent(cardStub).trigger('click')
    wrapper.unmount()
    pending.reject(new Error('late failure'))
    await flushPromises()

    expect(mocks.messageError).not.toHaveBeenCalled()
  })

  it('ignores stale provider list responses and failures after category changes', async () => {
    const requests = Array.from({ length: 5 }, () => deferred<{ data: { list: ReturnType<typeof provider>[] } }>())
    let requestIndex = 0
    mocks.getPublicMcpProvidersWithPage.mockImplementation(({ category }) => {
      if (!category) return Promise.resolve({ data: { list: [provider('initial')] } }) as never
      return requests[requestIndex++].promise as never
    })
    const wrapper = shallowMount(McpListView, { global: { stubs: globalStubs } })
    await flushPromises()
    const setupState = (wrapper.vm.$ as unknown as {
      setupState: { loading: boolean; providers: ReturnType<typeof provider>[] }
    }).setupState
    const clickCategory = async (name: string) =>
      wrapper.findAllComponents(buttonStub).find((item) => item.text() === name)!.trigger('click')

    await clickCategory('编程工具')
    await clickCategory('媒体音视频')
    requests[1].resolve({ data: { list: [provider('media-result')] } })
    await flushPromises()
    requests[0].resolve({ data: { list: [provider('stale-result')] } })
    await flushPromises()
    expect(wrapper.text()).toContain('media-result')
    expect(wrapper.text()).not.toContain('stale-result')

    await clickCategory('编程工具')
    await clickCategory('媒体音视频')
    requests[2].reject(new Error('stale failure'))
    await flushPromises()
    expect(setupState.loading).toBe(true)
    expect(mocks.messageError).not.toHaveBeenCalled()
    requests[3].resolve({ data: { list: [provider('media-latest')] } })
    await flushPromises()
    expect(wrapper.text()).toContain('media-latest')

    await clickCategory('编程工具')
    const providersBeforeUnmount = setupState.providers
    wrapper.unmount()
    requests[4].resolve({ data: { list: [provider('late-after-unmount')] } })
    await flushPromises()
    expect(setupState.providers).toBe(providersBeforeUnmount)
  })
})
