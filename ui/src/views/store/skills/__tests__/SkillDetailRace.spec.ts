import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getSkill, getSkillsWithPage, getSkillCategories } = vi.hoisted(() => ({
  getSkill: vi.fn(),
  getSkillsWithPage: vi.fn(),
  getSkillCategories: vi.fn(),
}))

vi.mock('@arco-design/web-vue', () => ({ Message: { error: vi.fn() } }))
vi.mock('@/services/skill', () => ({ getSkill, getSkillsWithPage, getSkillCategories }))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const skill = (id: string, label: string) => ({
  id, label, name: label, source_key: id, description: '', icon: '', category: 'general',
  executor_type: 'prompt', tool_count: 0, tags: [], tools: [], readme: '', bundle: {}, capabilities: {},
})

describe('Skills list detail requests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getSkillCategories.mockResolvedValue({ data: { categories: [] } })
    getSkillsWithPage.mockResolvedValue({ data: { list: [skill('a', 'Skill A'), skill('b', 'Skill B')], paginator: { total_page: 1 } } })
  })

  it('keeps the latest selected skill when an older request resolves last', async () => {
    const requestA = deferred<{ data: ReturnType<typeof skill> }>()
    const requestB = deferred<{ data: ReturnType<typeof skill> }>()
    getSkill.mockReturnValueOnce(requestA.promise).mockReturnValueOnce(requestB.promise)
    const { default: ListView } = await import('../ListView.vue')
    const wrapper = mount(ListView, { global: { stubs: {
      'a-card': defineComponent({ emits: ['click'], setup(_props, { emit, slots }) { return () => h('div', { onClick: () => emit('click') }, slots.default?.()) } }),
      'a-drawer': defineComponent({ props: ['visible'], setup(props, { slots }) { return () => props.visible ? h('div', slots.default?.()) : null } }),
      'resource-card-description': true,
    } } })
    await flushPromises()

    const cards = wrapper.findAll('[class*="cursor-pointer rounded-lg"]')
    await cards[0].trigger('click')
    await cards[1].trigger('click')
    requestB.resolve({ data: skill('b', 'Latest Skill B') })
    await flushPromises()
    requestA.resolve({ data: skill('a', 'Stale Skill A') })
    await flushPromises()

    expect(wrapper.text()).toContain('Latest Skill B')
    expect(wrapper.text()).not.toContain('Stale Skill A')
    wrapper.unmount()
  })
})
