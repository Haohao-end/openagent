import { flushPromises, mount } from '@vue/test-utils'
import { Message } from '@arco-design/web-vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick } from 'vue'

import McpMarketplacePickerModal from '../McpMarketplacePickerModal.vue'
import type { McpBinding } from '@/models/mcp'

const mocks = vi.hoisted(() => ({
  getPublicMcpCategories: vi.fn(),
  getPublicMcpProvidersWithPage: vi.fn(),
  messageError: vi.fn(),
}))

vi.mock('@/services/mcp', () => ({
  getPublicMcpCategories: (...args: unknown[]) => mocks.getPublicMcpCategories(...args),
  getPublicMcpProvidersWithPage: (...args: unknown[]) => mocks.getPublicMcpProvidersWithPage(...args),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    warning: vi.fn(),
    success: vi.fn(),
    error: mocks.messageError,
  },
}))

const makePaginator = (current_page: number, total_page: number, total_record: number) => ({
  current_page,
  total_page,
  total_record,
  page_size: 50,
})

const makeProvider = (provider_key: string, label: string, overrides: Record<string, unknown> = {}) => ({
  provider_key,
  label,
  name: label,
  description: `${label} 描述`,
  background: '#1677ff',
  icon: '',
  category: 'productivity',
  transport: 'streamable_http',
  creator_name: '公开目录',
  tool_count: 1,
  is_bindable: true,
  binding: {
    transport: 'streamable_http',
    url: `https://example.com/${provider_key}`,
    command: '',
    name: label,
    provider_key,
  },
  ...overrides,
})

const makeSelectedBinding = (provider_key: string): McpBinding => ({
  name: '12306-mcp',
  description: '12306 MCP',
  transport: 'streamable_http',
  url: `https://example.com/${provider_key}`,
  command: '',
  enabled: true,
  headers: [],
  tool_names: [],
  timeout_seconds: 30,
  args: [],
  env: {},
  provider_key,
})

const setScrollMetrics = (
  element: HTMLElement,
  metrics: { scrollTop: number; clientHeight: number; scrollHeight: number },
) => {
  Object.defineProperty(element, 'scrollTop', {
    configurable: true,
    value: metrics.scrollTop,
  })
  Object.defineProperty(element, 'clientHeight', {
    configurable: true,
    value: metrics.clientHeight,
  })
  Object.defineProperty(element, 'scrollHeight', {
    configurable: true,
    value: metrics.scrollHeight,
  })
}

const buttonStub = defineComponent({
  props: {
    disabled: { type: Boolean, default: false },
  },
  emits: ['click'],
  template: "<button :disabled=\"disabled\" @click=\"$emit('click', $event)\"><slot /></button>",
})

const inputSearchStub = defineComponent({
  props: {
    modelValue: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'search'],
  template:
    "<div><input data-testid=\"search-input\" :value=\"modelValue\" @input=\"$emit('update:modelValue', $event.target.value)\" /><button data-testid=\"search-button\" @click=\"$emit('search')\">search</button></div>",
})

const modalStub = { template: '<div><slot /></div>' }
const spinStub = { template: '<div><slot /></div>' }
const avatarStub = { template: '<div><slot /></div>' }
const tagStub = { template: '<span><slot /></span>' }
const spaceStub = { template: '<div><slot /></div>' }
const emptyStub = { template: '<div><slot /></div>' }

const globalStubs = {
  'a-modal': modalStub,
  'a-button': buttonStub,
  'a-input-search': inputSearchStub,
  'a-spin': spinStub,
  'a-avatar': avatarStub,
  'a-tag': tagStub,
  'a-space': spaceStub,
  'a-empty': emptyStub,
  'icon-apps': true,
}

describe('McpMarketplacePickerModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads the first page and appends the next page on scroll', async () => {
    mocks.getPublicMcpCategories.mockResolvedValue({ data: { categories: [{ id: 'cat-1', name: '分类一' }] } })
    mocks.getPublicMcpProvidersWithPage.mockImplementation(async (params: Record<string, unknown>) => {
      if (Number(params.current_page) === 1) {
        return {
          data: {
            list: [makeProvider('provider-1', '12306 MCP'), makeProvider('provider-2', '天气 MCP')],
            paginator: makePaginator(1, 2, 3),
          },
        }
      }

      if (Number(params.current_page) === 2) {
        return {
          data: {
            list: [makeProvider('provider-3', '路线 MCP')],
            paginator: makePaginator(2, 2, 3),
          },
        }
      }

      throw new Error(`unexpected page: ${String(params.current_page)}`)
    })

    const wrapper = mount(McpMarketplacePickerModal, {
      props: {
        visible: true,
        selected_bindings: [makeSelectedBinding('provider-1')],
      },
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()
    await nextTick()

    expect(mocks.getPublicMcpCategories).toHaveBeenCalled()
    expect(mocks.getPublicMcpProvidersWithPage).toHaveBeenCalledWith(
      expect.objectContaining({
        current_page: 1,
        page_size: 50,
        search_word: '',
        category: '',
      }),
    )
    expect(wrapper.text()).toContain('12306 MCP')
    expect(wrapper.text()).toContain('效率工具')
    expect(wrapper.text()).toContain('公开目录')
    expect(wrapper.text()).toContain('个工具')
    expect(wrapper.text()).toContain('已添加')
    expect(wrapper.text()).toContain('添加到应用')

    const list = wrapper.get('[data-testid="mcp-binding-list"]').element as HTMLElement
    setScrollMetrics(list, {
      scrollTop: 1000,
      clientHeight: 400,
      scrollHeight: 1300,
    })
    await wrapper.get('[data-testid="mcp-binding-list"]').trigger('scroll')
    await flushPromises()
    await nextTick()

    expect(mocks.getPublicMcpProvidersWithPage).toHaveBeenCalledWith(
      expect.objectContaining({
        current_page: 2,
        page_size: 50,
        search_word: '',
        category: '',
      }),
    )
    expect(wrapper.text()).toContain('路线 MCP')
  })

  it('starts a new first-page request when search changes during loading', async () => {
    let resolveInitial!: (value: unknown) => void
    const initialRequest = new Promise((resolve) => { resolveInitial = resolve })
    mocks.getPublicMcpCategories.mockResolvedValue({ data: { categories: [] } })
    mocks.getPublicMcpProvidersWithPage.mockReturnValueOnce(initialRequest).mockResolvedValueOnce({
      data: {
        list: [makeProvider('latest-provider', 'Latest provider')],
        paginator: makePaginator(1, 1, 1),
      },
    })

    const wrapper = mount(McpMarketplacePickerModal, {
      props: { visible: true, selected_bindings: [] },
      global: { stubs: globalStubs },
    })
    await flushPromises()
    await wrapper.get('[data-testid="search-input"]').setValue('latest')
    await wrapper.get('[data-testid="search-button"]').trigger('click')

    expect(mocks.getPublicMcpProvidersWithPage).toHaveBeenCalledTimes(2)
    expect(mocks.getPublicMcpProvidersWithPage.mock.calls[1][0]).toMatchObject({ search_word: 'latest', current_page: 1 })

    resolveInitial({
      data: {
        list: [makeProvider('stale-provider', 'Stale provider')],
        paginator: makePaginator(1, 1, 1),
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Latest provider')
    expect(wrapper.text()).not.toContain('Stale provider')
    wrapper.unmount()
  })

  it('ignores provider errors that arrive after the picker closes', async () => {
    let rejectProviders!: (error: Error) => void
    mocks.getPublicMcpCategories.mockResolvedValue({ data: { categories: [] } })
    mocks.getPublicMcpProvidersWithPage.mockReturnValue(new Promise((_resolve, reject) => { rejectProviders = reject }))

    const wrapper = mount(McpMarketplacePickerModal, {
      props: { visible: true, selected_bindings: [] },
      global: { stubs: globalStubs },
    })
    await flushPromises()
    await wrapper.setProps({ visible: false })

    rejectProviders(new Error('stale provider failure'))
    await flushPromises()

    expect(Message.error).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
