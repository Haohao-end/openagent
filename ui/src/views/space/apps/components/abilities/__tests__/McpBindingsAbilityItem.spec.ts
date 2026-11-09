import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import McpBindingsAbilityItem from '../McpBindingsAbilityItem.vue'

const mocks = vi.hoisted(() => ({
  updateDraftAppConfig: vi.fn().mockResolvedValue({}),
}))

vi.mock('@/hooks/use-app', () => ({
  useUpdateDraftAppConfig: () => ({
    handleUpdateDraftAppConfig: mocks.updateDraftAppConfig,
  }),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    warning: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const slotStub = {
  template: '<div><slot /><slot name="header" /><slot name="extra" /></div>',
}

const globalStubs = {
  'a-collapse-item': slotStub,
  'a-button': slotStub,
  'a-tag': slotStub,
  'a-tooltip': slotStub,
  'a-modal': slotStub,
  'a-input': slotStub,
  'a-textarea': slotStub,
  'a-select': slotStub,
  'a-option': slotStub,
  'a-input-number': slotStub,
  'a-switch': slotStub,
  'a-spin': slotStub,
  'mcp-marketplace-picker-modal': true,
  'icon-plus': slotStub,
  'icon-close': slotStub,
  'icon-delete': slotStub,
  'icon-question-circle': slotStub,
}

const makeBinding = (overrides: Record<string, unknown> = {}) => ({
  name: '12306-mcp',
  description: '12306 车票查询 MCP',
  transport: 'streamable_http',
  url: 'https://mcp.api-inference.modelscope.net/540c010e843a4e/mcp',
  command: '',
  enabled: true,
  headers: [],
  tool_names: [],
  timeout_seconds: 30,
  args: [],
  env: {},
  provider_key: 'catalog::QEpvb29vb2svMTIzMDYtbWNw',
  source_type: 'catalog',
  source_key: '@Joooook/12306-mcp',
  source_url: 'https://www.modelscope.cn/mcp/servers/@Joooook/12306-mcp',
  label: '12306 车票查询 MCP',
  icon: '',
  category: 'productivity',
  ...overrides,
})

const makeSnapshot = (overrides: Record<string, unknown> = {}) => ({
  binding_identity: 'catalog::QEpvb29vb2svMTIzMDYtbWNw',
  binding_hash: 'binding-hash',
  binding: makeBinding(),
  status: 'ready',
  tool_definitions: [{}],
  tool_names: ['query_train_info'],
  tool_count: 1,
  schema_hash: 'schema-hash',
  last_attempt_at: 1710000000,
  last_success_at: 1710000000,
  last_error: '',
  retry_count: 0,
  retryable: false,
  ...overrides,
})

describe('McpBindingsAbilityItem', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('re-syncs bindings when the draft config arrives after the initial empty render', async () => {
    const wrapper = mount(McpBindingsAbilityItem, {
      props: {
        app_id: 'app-1',
        mcp_bindings: [],
        mcp_tool_snapshots: [],
      },
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()
    expect(wrapper.find('.text-gray-700.font-bold').text()).toBe('MCP')
    expect(wrapper.text()).toContain('点击右上角 + 从 MCP 广场添加 MCP')

    await wrapper.setProps({
      mcp_bindings: [makeBinding()],
      mcp_tool_snapshots: [makeSnapshot({ status: 'warming', tool_count: 0, tool_definitions: [] })],
    })
    await nextTick()
    await flushPromises()

    expect(wrapper.text()).toContain('12306-mcp')
    expect(wrapper.text()).toContain('12306 车票查询 MCP')
    expect(wrapper.text()).toContain('预热中')
  })

  it('shows ready status when the binding snapshot is available', async () => {
    const wrapper = mount(McpBindingsAbilityItem, {
      props: {
        app_id: 'app-1',
        mcp_bindings: [makeBinding()],
        mcp_tool_snapshots: [makeSnapshot()],
      },
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('已可用')
    expect(wrapper.text()).not.toContain('已启用')
    expect(wrapper.text()).not.toContain('已停用')
  })

  it('includes an earlier marketplace selection when a second save overlaps', async () => {
    let resolveFirst!: () => void
    const firstSave = new Promise<void>((resolve) => { resolveFirst = resolve })
    mocks.updateDraftAppConfig.mockReset().mockReturnValueOnce(firstSave).mockResolvedValue({})
    const wrapper = mount(McpBindingsAbilityItem, {
      props: { app_id: 'app-1', mcp_bindings: [], mcp_tool_snapshots: [] },
      global: { stubs: globalStubs },
    })
    const state = (wrapper.vm.$ as any).setupState
    const firstBinding = makeBinding({ name: 'First MCP', provider_key: 'catalog::first' })
    const secondBinding = makeBinding({ name: 'Second MCP', provider_key: 'catalog::second' })
    const firstSelection = state.handleSelectMarketplaceBinding(firstBinding)
    const secondSelection = state.handleSelectMarketplaceBinding(secondBinding)
    await nextTick()
    const requestsWhileFirstSavePending = mocks.updateDraftAppConfig.mock.calls.length
    resolveFirst()
    await Promise.all([firstSelection, secondSelection])
    const secondRequestBindings = mocks.updateDraftAppConfig.mock.calls[1]?.[1].mcp_bindings.map((item: any) => item.provider_key)
    expect(requestsWhileFirstSavePending).toBe(1)
    expect(secondRequestBindings).toEqual(['catalog::first', 'catalog::second'])
    expect(state.activateMcpBindings.map((item: any) => item.provider_key)).toEqual(['catalog::first', 'catalog::second'])
    wrapper.unmount()
  })

  it('keeps the binding editor open while its save is pending', async () => {
    let resolveSave!: () => void
    const pendingSave = new Promise<void>((resolve) => { resolveSave = resolve })
    mocks.updateDraftAppConfig.mockReturnValueOnce(pendingSave)
    const wrapper = mount(McpBindingsAbilityItem, {
      props: { app_id: 'app-1', mcp_bindings: [makeBinding()], mcp_tool_snapshots: [] },
      global: { stubs: globalStubs },
    })
    const state = (wrapper.vm.$ as any).setupState
    state.openEditModal(0)
    const submit = state.handleSubmitBinding()
    await nextTick()

    state.handleCancelMcpBindingsModal()

    expect(state.mcpBindingsModalVisible).toBe(true)
    resolveSave()
    await submit
    expect(state.mcpBindingsModalVisible).toBe(false)
    wrapper.unmount()
  })

  it('prevents overlapping MCP binding deletions', async () => {
    let resolveDelete!: () => void
    const pendingDelete = new Promise<void>((resolve) => { resolveDelete = resolve })
    mocks.updateDraftAppConfig.mockReturnValueOnce(pendingDelete)
    const wrapper = mount(McpBindingsAbilityItem, {
      props: {
        app_id: 'app-1',
        mcp_bindings: [makeBinding({ provider_key: 'catalog::first' }), makeBinding({ provider_key: 'catalog::second' })],
        mcp_tool_snapshots: [],
      },
      global: { stubs: globalStubs },
    })
    const state = (wrapper.vm.$ as any).setupState
    const firstDelete = state.handleDeleteBinding(0)
    const secondDelete = state.handleDeleteBinding(1)

    expect(mocks.updateDraftAppConfig).toHaveBeenCalledTimes(1)
    resolveDelete()
    await Promise.all([firstDelete, secondDelete])
    expect(state.activateMcpBindings.map((item: any) => item.provider_key)).toEqual(['catalog::second'])
    wrapper.unmount()
  })
})
