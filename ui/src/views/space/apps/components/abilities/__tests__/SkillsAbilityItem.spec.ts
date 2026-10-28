import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import SkillsAbilityItem from '../SkillsAbilityItem.vue'

const mocks = vi.hoisted(() => ({
  updateDraftAppConfig: vi.fn().mockResolvedValue({}),
  getSkill: vi.fn(),
  messageError: vi.fn(),
}))

vi.mock('@/hooks/use-app', () => ({
  useUpdateDraftAppConfig: () => ({
    handleUpdateDraftAppConfig: mocks.updateDraftAppConfig,
  }),
}))

vi.mock('@/services/skill', () => ({
  getSkill: (...args: unknown[]) => mocks.getSkill(...args),
}))

vi.mock('@/hooks/use-markdown-renderer', () => ({
  useMarkdownRenderer: () => ({
    renderMarkdown: (value: string) => value,
  }),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    warning: vi.fn(),
    success: vi.fn(),
    error: mocks.messageError,
  },
}))

const slotStub = {
  template: '<div><slot /><slot name="header" /><slot name="extra" /></div>',
}

const globalStubs = {
  'a-collapse-item': slotStub,
  'a-button': slotStub,
  'a-tag': slotStub,
  'a-modal': slotStub,
  'a-spin': slotStub,
  'a-avatar': slotStub,
  'a-card': slotStub,
  'a-select': slotStub,
  'a-option': slotStub,
  'a-switch': slotStub,
  'icon-plus': slotStub,
  'icon-close': slotStub,
  'icon-delete': slotStub,
  'skills-marketplace-picker-modal': slotStub,
}

const makeSkillBinding = (overrides: Record<string, unknown> = {}) => ({
  id: 'skill-1',
  skill_id: 'skill-1',
  source_key: 'code_workbench',
  name: '代码工坊',
  label: '代码工坊',
  icon: '',
  description: '面向代码分析、补丁生成、文件输出和自动化脚本执行的技能包。',
  readme: '# 代码工坊\n\n面向代码分析。',
  category: '开发',
  tags: ['代码'],
  capabilities: { code: true },
  executor_type: 'scf',
  tool_count: 3,
  tools: [],
  created_at: 0,
  updated_at: 0,
  ...overrides,
})

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}

describe('SkillsAbilityItem', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getSkill.mockResolvedValue({
      data: makeSkillBinding(),
    })
  })

  it('renders bound skills from props and rehydrates after prop updates', async () => {
    const wrapper = mount(SkillsAbilityItem, {
      props: {
        app_id: 'app-1',
        skills: [makeSkillBinding()],
      },
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('代码工坊')
    expect(wrapper.text()).toContain('code_workbench')
    expect(wrapper.text()).toContain('3 个工具')
    expect(wrapper.text()).toContain('SCF')
    expect(wrapper.text()).toContain('面向代码分析、补丁生成、文件输出和自动化脚本执行的技能包。')

    await wrapper.setProps({
      skills: [makeSkillBinding({ label: '代码工坊 Pro', description: '新摘要' })],
    })
    await nextTick()
    await flushPromises()

    expect(wrapper.text()).toContain('代码工坊 Pro')
    expect(wrapper.text()).toContain('新摘要')
  })

  it('keeps the latest selected skill detail when an earlier request resolves last', async () => {
    const olderRequest = deferred<{ data: ReturnType<typeof makeSkillBinding> }>()
    mocks.getSkill.mockReturnValueOnce(olderRequest.promise).mockResolvedValueOnce({
      data: makeSkillBinding({ id: 'skill-2', skill_id: 'skill-2', label: 'Latest skill', readme: 'latest content' }),
    })
    const wrapper = mount(SkillsAbilityItem, {
      props: {
        app_id: 'app-1',
        skills: [
          makeSkillBinding({ id: 'skill-1', skill_id: 'skill-1', label: 'First skill' }),
          makeSkillBinding({ id: 'skill-2', skill_id: 'skill-2', label: 'Second skill' }),
        ],
      },
      global: { stubs: globalStubs },
    })
    await flushPromises()

    const skillRows = wrapper.findAll('.cursor-pointer').filter((row) => /First skill|Second skill/.test(row.text()))
    await skillRows[0].trigger('click')
    await skillRows[1].trigger('click')
    await flushPromises()
    olderRequest.resolve({ data: makeSkillBinding({ label: 'Stale skill', readme: 'stale content' }) })
    await flushPromises()

    expect(wrapper.find('.skill-markdown').text()).toBe('latest content')
    wrapper.unmount()
  })

  it('ignores an earlier detail failure after a newer skill was selected', async () => {
    const olderRequest = deferred<{ data: ReturnType<typeof makeSkillBinding> }>()
    mocks.getSkill.mockReturnValueOnce(olderRequest.promise).mockResolvedValueOnce({
      data: makeSkillBinding({ id: 'skill-2', skill_id: 'skill-2', label: 'Latest skill', readme: 'latest content' }),
    })
    const wrapper = mount(SkillsAbilityItem, {
      props: {
        app_id: 'app-1',
        skills: [
          makeSkillBinding({ id: 'skill-1', skill_id: 'skill-1', label: 'First skill' }),
          makeSkillBinding({ id: 'skill-2', skill_id: 'skill-2', label: 'Second skill' }),
        ],
      },
      global: { stubs: globalStubs },
    })
    await flushPromises()

    const skillRows = wrapper.findAll('.cursor-pointer').filter((row) => /First skill|Second skill/.test(row.text()))
    await skillRows[0].trigger('click')
    await skillRows[1].trigger('click')
    await flushPromises()
    olderRequest.reject(new Error('stale request failure'))
    await flushPromises()

    expect(mocks.messageError).not.toHaveBeenCalled()
    expect(wrapper.find('.skill-markdown').text()).toBe('latest content')
    wrapper.unmount()
  })
})
