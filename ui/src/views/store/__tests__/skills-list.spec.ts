import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import SkillsListView from '@/views/store/skills/ListView.vue'

const mocks = vi.hoisted(() => ({
  getSkillCategories: vi.fn(),
  getSkillsWithPage: vi.fn(),
  getSkill: vi.fn(),
}))

vi.mock('@/config', () => ({
  apiPrefix: 'https://api.example.com',
}))

vi.mock('@/services/skill', () => ({
  getSkillCategories: mocks.getSkillCategories,
  getSkillsWithPage: mocks.getSkillsWithPage,
  getSkill: mocks.getSkill,
}))

const slotStub = {
  template: '<div><slot /></div>',
}

const buttonStub = {
  emits: ['click'],
  template: '<button type="button" v-bind="$attrs" @click="$emit(\'click\', $event)"><slot /></button>',
}

const globalStubs = {
  'a-spin': slotStub,
  'a-avatar': slotStub,
  'a-button': buttonStub,
  'a-tag': slotStub,
  'a-card': slotStub,
  'a-col': slotStub,
  'a-empty': slotStub,
  'a-row': slotStub,
  'a-drawer': slotStub,
  'a-input-search': {
    template: '<input />',
  },
  'card-grid-skeleton': slotStub,
  'resource-card-description': slotStub,
  'icon-storage': slotStub,
  'icon-file': slotStub,
  'icon-plus': slotStub,
  'icon-close': slotStub,
}

describe('skills store list', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mocks.getSkillCategories.mockResolvedValue({
      data: {
        categories: [{ id: '开发', name: '开发', count: 1 }],
      },
    })

    mocks.getSkillsWithPage.mockResolvedValue({
      data: {
        list: [
          {
            id: 'skill-1',
            source_key: 'code_workbench',
            source_path: '/tmp/code_workbench',
            name: '代码工坊',
            label: '代码工坊',
            icon: '/skills/skill-1/icon.svg',
            description: '代码分析与文件输出',
            readme: '# 代码工坊\n\n用于代码分析与文件输出。',
            category: '开发',
            tags: ['代码'],
            capabilities: { code: true },
            executor_type: 'scf',
            tool_count: 1,
            tools: [],
            created_at: 1710000000,
            updated_at: 1710000000,
          },
        ],
        paginator: {
          current_page: 1,
          page_size: 20,
          total_page: 1,
          total_record: 1,
        },
      },
    })
  })

  it('renders skill cards with api-prefixed icons', async () => {
    const wrapper = shallowMount(SkillsListView, {
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()

    expect(mocks.getSkillCategories).toHaveBeenCalledTimes(1)
    expect(mocks.getSkillsWithPage).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Skills 广场')
    expect(wrapper.text()).not.toContain('本地技能包目录')
    expect(wrapper.text()).not.toContain('当前版本')
    expect(wrapper.text()).not.toContain('版本历史')
    expect(wrapper.text()).toContain('全部')
    expect(wrapper.html()).toContain('rounded-lg !text-gray-700 px-3')
    expect(wrapper.html()).not.toContain('skills-category-btn')

    const img = wrapper.find('img[alt="代码工坊"]')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('https://api.example.com/skills/skill-1/icon.svg')
  })

  it('hides tool count text when a skill has zero tools', async () => {
    mocks.getSkillsWithPage.mockResolvedValueOnce({
      data: {
        list: [
          {
            id: 'skill-2',
            source_key: 'frontend-skill',
            source_path: '/tmp/frontend-skill',
            name: '前端技能',
            label: '前端技能',
            icon: '',
            description: '用于视觉层次与动效的前端技能',
            readme: '# 前端技能\n\n只保留提示词。',
            category: '设计',
            tags: ['github', 'curated', 'prompt-only'],
            capabilities: {},
            executor_type: 'prompt',
            tool_count: 0,
            tools: [],
            created_at: 1710000000,
            updated_at: 1710000000,
          },
        ],
        paginator: {
          current_page: 1,
          page_size: 20,
          total_page: 1,
          total_record: 1,
        },
      },
    })

    const wrapper = shallowMount(SkillsListView, {
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('前端技能')
    expect(wrapper.text()).not.toContain('个工具')
  })

  it('renders a richer fallback avatar when icon is missing', async () => {
    mocks.getSkillsWithPage.mockResolvedValueOnce({
      data: {
        list: [
          {
            id: 'skill-3',
            source_key: 'git-guardrails-claude-code',
            source_path: '/tmp/git-guardrails',
            name: 'git-guardrails',
            label: 'Git Guardrails',
            icon: '',
            description: 'Git safety rules',
            readme: '# Git Guardrails\n\nAvoid destructive git actions.',
            category: '安全',
            tags: ['github', 'curated', 'prompt-only'],
            capabilities: {},
            executor_type: 'prompt',
            tool_count: 0,
            tools: [],
            created_at: 1710000000,
            updated_at: 1710000000,
          },
        ],
        paginator: {
          current_page: 1,
          page_size: 20,
          total_page: 1,
          total_record: 1,
        },
      },
    })

    const wrapper = shallowMount(SkillsListView, {
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('GG')
  })

  it('retries the same page after an infinite-scroll request fails', async () => {
    mocks.getSkillsWithPage
      .mockResolvedValueOnce({ data: { list: [], paginator: { total_page: 2 } } })
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce({ data: { list: [], paginator: { total_page: 2 } } })
    const wrapper = shallowMount(SkillsListView, { global: { stubs: globalStubs } })
    await flushPromises()

    const list = wrapper.find('.overflow-y-auto')
    await list.trigger('scroll')
    await flushPromises()
    await list.trigger('scroll')
    await flushPromises()

    expect(mocks.getSkillsWithPage.mock.calls.map(([params]) => params.current_page)).toEqual([1, 2, 2])
  })
})
