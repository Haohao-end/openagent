import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import StoreToolsListView from '@/views/store/tools/ListView.vue'

const mocks = vi.hoisted(() => ({
  getCategories: vi.fn(),
  getBuiltinTools: vi.fn(),
}))

vi.mock('@/config', () => ({
  apiPrefix: 'https://api.example.com',
  typeMap: {
    string: '字符串',
    number: '数字',
    boolean: '布尔值',
  },
}))

vi.mock('@/services/builtin-tool', () => ({
  getCategories: mocks.getCategories,
  getBuiltinTools: mocks.getBuiltinTools,
}))

const slotStub = {
  template: '<div><slot /></div>',
}

const globalStubs = {
  'a-spin': slotStub,
  'a-avatar': slotStub,
  'a-button': slotStub,
  'a-input-search': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'a-row': slotStub,
  'a-col': slotStub,
  'a-card': slotStub,
  'a-empty': slotStub,
  'a-drawer': slotStub,
  'router-link': {
    template: '<a><slot /></a>',
  },
  'icon-common': slotStub,
  'icon-user': slotStub,
}

describe('store tools list', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mocks.getCategories.mockResolvedValue({
      data: [
        { category: 'search', icon: 'search.svg', name: '搜索' },
        { category: 'code', icon: 'code.svg', name: '编程' },
      ],
    })

    mocks.getBuiltinTools.mockResolvedValue({
      data: [
        {
          background: '#dbeafe',
          category: 'search',
          created_at: 1710000000,
          description: '用于搜索和查询的工具提供商',
          label: '搜索工具',
          name: 'search_provider',
          tools: [
            {
              name: 'search_web',
              label: 'Web 搜索',
              description: '搜索网页结果',
              inputs: [],
            },
          ],
        },
        {
          background: '#e0e7ff',
          category: 'code',
          created_at: 1710000100,
          description: '用于代码相关任务的工具提供商',
          label: '代码工具',
          name: 'code_provider',
          tools: [],
        },
      ],
    })
  })

  it('renders a scrollable tool list container', async () => {
    const wrapper = shallowMount(StoreToolsListView, {
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()

    expect(mocks.getCategories).toHaveBeenCalledTimes(1)
    expect(mocks.getBuiltinTools).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('插件广场')

    const scrollContainer = wrapper.find('.overflow-y-auto')
    expect(scrollContainer.exists()).toBe(true)
    expect(scrollContainer.classes()).toContain('scrollbar-w-none')
    expect(scrollContainer.text()).toContain('搜索工具')
    expect(scrollContainer.text()).toContain('代码工具')
  })

  it('matches builtin tool labels without case sensitivity', async () => {
    mocks.getBuiltinTools.mockResolvedValueOnce({
      data: [{ background: '#fff', category: 'search', label: 'GitHub Search', name: 'github_search', tools: [] }],
    })
    const wrapper = shallowMount(StoreToolsListView, { global: { stubs: globalStubs } })

    await flushPromises()
    await wrapper.find('input').setValue('Search')

    expect(wrapper.text()).toContain('GitHub Search')
  })
})
