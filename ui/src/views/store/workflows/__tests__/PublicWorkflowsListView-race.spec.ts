import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockGetPublicWorkflows, mockGetAppTags } = vi.hoisted(() => ({
  mockGetPublicWorkflows: vi.fn(),
  mockGetAppTags: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: vi.fn(), success: vi.fn() } }))
vi.mock('@/services/public-workflow', () => ({
  getPublicWorkflows: mockGetPublicWorkflows,
  forkPublicWorkflow: vi.fn(),
}))
vi.mock('@/services/public-app', () => ({ getAppTags: mockGetAppTags }))

const SearchStub = defineComponent({
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue', 'search'],
  setup(props, { emit }) {
    return () => h('div', [
      h('input', {
        'data-testid': 'workflow-search',
        value: props.modelValue,
        onInput: (event: Event) => emit('update:modelValue', (event.target as HTMLInputElement).value),
      }),
      h('button', { 'data-testid': 'workflow-search-submit', onClick: () => emit('search') }),
    ])
  },
})

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise })
  return { promise, resolve }
}

const response = (id: string, name: string) => ({
  data: {
    list: [{ id, name, icon: '', description: '', tags: [], published_at: 0, created_at: 0, account_name: '', account_avatar: '' }],
    paginator: { total_page: 1 },
  },
})

describe('PublicWorkflowsListView request ordering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetAppTags.mockResolvedValue({ data: { tags: [] } })
  })

  it('runs the latest search and ignores the stale list response', async () => {
    const oldRequest = deferred<ReturnType<typeof response>>()
    const newRequest = deferred<ReturnType<typeof response>>()
    mockGetPublicWorkflows.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)

    const { default: ListView } = await import('../ListView.vue')
    const wrapper = mount(ListView, { global: { stubs: { 'a-input-search': SearchStub } } })
    await flushPromises()

    await wrapper.get('[data-testid="workflow-search"]').setValue('latest')
    await wrapper.get('[data-testid="workflow-search-submit"]').trigger('click')
    await nextTick()

    expect(mockGetPublicWorkflows).toHaveBeenCalledTimes(2)
    expect(mockGetPublicWorkflows.mock.calls[1][0].search_word).toBe('latest')

    newRequest.resolve(response('new-workflow', 'Latest Workflow'))
    await flushPromises()
    oldRequest.resolve(response('old-workflow', 'Stale Workflow'))
    await flushPromises()

    expect(wrapper.text()).toContain('Latest Workflow')
    expect(wrapper.text()).not.toContain('Stale Workflow')
    wrapper.unmount()
  })
})
