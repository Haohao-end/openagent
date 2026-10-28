import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick } from 'vue'

import SkillsMarketplacePickerModal from '../SkillsMarketplacePickerModal.vue'
import type { SkillBinding, SkillPackage } from '@/models/skill'

const mocks = vi.hoisted(() => ({
  getSkillCategories: vi.fn(),
  getSkillsWithPage: vi.fn(),
}))

vi.mock('@/services/skill', () => ({
  getSkillCategories: (...args: unknown[]) => mocks.getSkillCategories(...args),
  getSkillsWithPage: (...args: unknown[]) => mocks.getSkillsWithPage(...args),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    warning: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const makePaginator = (current_page: number, total_page: number, total_record: number) => ({
  current_page,
  total_page,
  total_record,
  page_size: 50,
})

const makeSkill = (
  id: string,
  label: string,
  overrides: Record<string, unknown> = {},
): SkillPackage => ({
  id,
  source_key: `source::${id}`,
  name: label,
  label,
  icon: '',
  description: `${label} 描述`,
  readme: '',
  category: 'productivity',
  tags: [],
  capabilities: {},
  executor_type: 'tool',
  tool_count: 1,
  tools: [],
  created_at: 1710000000,
  updated_at: 1710000000,
  ...overrides,
})

const makeSelectedBinding = (skillId: string): SkillBinding => ({
  ...makeSkill(skillId, skillId),
  skill_id: skillId,
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

describe('SkillsMarketplacePickerModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads the first page and appends the next page on scroll', async () => {
    mocks.getSkillCategories.mockResolvedValue({ data: { categories: [{ id: 'cat-1', name: '分类一' }] } })
    mocks.getSkillsWithPage.mockImplementation(async (params: Record<string, unknown>) => {
      if (Number(params.current_page) === 1) {
        return {
          data: {
            list: [makeSkill('skill-1', '旅行规划师'), makeSkill('skill-2', '城市路线师')],
            paginator: makePaginator(1, 2, 3),
          },
        }
      }

      if (Number(params.current_page) === 2) {
        return {
          data: {
            list: [makeSkill('skill-3', '周末安排师')],
            paginator: makePaginator(2, 2, 3),
          },
        }
      }

      throw new Error(`unexpected page: ${String(params.current_page)}`)
    })

    const wrapper = mount(SkillsMarketplacePickerModal, {
      props: {
        visible: true,
        selected_bindings: [makeSelectedBinding('skill-1')],
      },
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()
    await nextTick()

    expect(mocks.getSkillCategories).toHaveBeenCalled()
    expect(mocks.getSkillsWithPage).toHaveBeenCalledWith(
      expect.objectContaining({
        current_page: 1,
        page_size: 50,
        search_word: '',
        category: '',
      }),
    )
    expect(wrapper.text()).toContain('旅行规划师')
    expect(wrapper.text()).toContain('已添加')

    const list = wrapper.get('[data-testid="skills-binding-list"]').element as HTMLElement
    setScrollMetrics(list, {
      scrollTop: 1000,
      clientHeight: 400,
      scrollHeight: 1300,
    })
    await wrapper.get('[data-testid="skills-binding-list"]').trigger('scroll')
    await flushPromises()
    await nextTick()

    expect(mocks.getSkillsWithPage).toHaveBeenCalledWith(
      expect.objectContaining({
        current_page: 2,
        page_size: 50,
        search_word: '',
        category: '',
      }),
    )
    expect(wrapper.text()).toContain('周末安排师')
  })

  it('starts a new first-page request when search changes during loading', async () => {
    let resolveInitial!: (value: unknown) => void
    const initialRequest = new Promise((resolve) => { resolveInitial = resolve })
    mocks.getSkillCategories.mockResolvedValue({ data: { categories: [] } })
    mocks.getSkillsWithPage.mockReturnValueOnce(initialRequest).mockResolvedValueOnce({
      data: { list: [makeSkill('new', 'New Search Result')], paginator: makePaginator(1, 1, 1) },
    })

    const wrapper = mount(SkillsMarketplacePickerModal, {
      props: { visible: true, selected_bindings: [] },
      global: { stubs: globalStubs },
    })
    await nextTick()
    await wrapper.get('[data-testid="search-input"]').setValue('new query')
    await wrapper.get('[data-testid="search-button"]').trigger('click')

    expect(mocks.getSkillsWithPage).toHaveBeenCalledTimes(2)
    expect(mocks.getSkillsWithPage.mock.calls[1][0]).toMatchObject({ search_word: 'new query', current_page: 1 })

    resolveInitial({ data: { list: [makeSkill('old', 'Old Search Result')], paginator: makePaginator(1, 1, 1) } })
    await flushPromises()
    expect(wrapper.text()).toContain('New Search Result')
    expect(wrapper.text()).not.toContain('Old Search Result')
    wrapper.unmount()
  })
})
