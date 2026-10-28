import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, reactive } from 'vue'

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

const mocks = vi.hoisted(() => ({
  route: null as { params: { workflow_id: string } } | null,
  getDetail: vi.fn(),
  getGraph: vi.fn(),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  const { reactive } = await import('vue')
  mocks.route ??= reactive({ params: { workflow_id: 'workflow-a' } })
  return { ...actual, useRoute: () => mocks.route, useRouter: () => ({ push: vi.fn() }) }
})
vi.mock('@vue-flow/core', () => ({
  ConnectionMode: {}, Panel: { template: '<div><slot /></div>' },
  VueFlow: {
    props: ['nodes'],
    template: '<div data-testid="preview-graph"><span v-for="node in nodes" :key="node.id">{{ node.id }}</span><slot /></div>',
  },
  useVueFlow: () => ({
    onPaneReady: vi.fn(), onViewportChange: vi.fn(), onNodeClick: vi.fn(), onPaneClick: vi.fn(), onEdgeClick: vi.fn(),
  }),
}))
vi.mock('@vue-flow/background', () => ({ Background: { template: '<div />' } }))
vi.mock('@vue-flow/minimap', () => ({ MiniMap: { template: '<div />' } }))
vi.mock('@/services/public-workflow', () => ({
  getPublicWorkflowDetail: mocks.getDetail,
  getPublicWorkflowDraftGraph: mocks.getGraph,
}))
vi.mock('@/views/space/workflows/use-workflow-header', () => ({
  useWorkflowHeader: () => ({ forkLoading: { value: false }, headerBackRoute: '/', handleAddToMySpace: vi.fn() }),
}))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: vi.fn(), success: vi.fn() } }))

describe('Public workflow preview route reuse', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route ??= reactive({ params: { workflow_id: 'workflow-a' } })
    mocks.route!.params.workflow_id = 'workflow-a'
    mocks.getDetail.mockImplementation(async (id: string) => ({ data: { id, name: id, icon: '', account_avatar: '' } }))
    mocks.getGraph.mockImplementation(async (id: string) => ({ data: { nodes: [{ id: `node-${id}`, type: 'start' }], edges: [] } }))
  })

  it('reloads workflow details and graph when the route id changes', async () => {
    const { default: PreviewView } = await import('../PreviewView.vue')
    const wrapper = mount(PreviewView, { global: { stubs: { '*': true, VueFlow: false, 'router-link': true } } })
    await flushPromises()

    expect(mocks.getDetail).toHaveBeenCalledWith('workflow-a')
    expect(mocks.getGraph).toHaveBeenCalledWith('workflow-a')

    mocks.route!.params.workflow_id = 'workflow-b'
    await nextTick()
    await flushPromises()

    expect(mocks.getDetail).toHaveBeenCalledWith('workflow-b')
    expect(mocks.getGraph).toHaveBeenCalledWith('workflow-b')
    wrapper.unmount()
  })

  it('keeps the latest workflow details and graph when the previous graph resolves last', async () => {
    const detailA = deferred<{ data: { id: string; name: string; icon: string; account_avatar: string } }>()
    const detailB = deferred<{ data: { id: string; name: string; icon: string; account_avatar: string } }>()
    const graphA = deferred<{ data: { nodes: Array<{ id: string; type: string }>; edges: [] } }>()
    const graphB = deferred<{ data: { nodes: Array<{ id: string; type: string }>; edges: [] } }>()
    mocks.getDetail.mockImplementation((id: string) => id === 'workflow-a' ? detailA.promise : detailB.promise)
    mocks.getGraph.mockImplementation((id: string) => id === 'workflow-a' ? graphA.promise : graphB.promise)

    const { default: PreviewView } = await import('../PreviewView.vue')
    const wrapper = mount(PreviewView, { global: { stubs: { '*': true, VueFlow: false, 'router-link': true } } })
    detailA.resolve({ data: { id: 'workflow-a', name: 'workflow-a', icon: '', account_avatar: '' } })
    await flushPromises()
    expect(mocks.getGraph).toHaveBeenCalledWith('workflow-a')

    mocks.route!.params.workflow_id = 'workflow-b'
    await nextTick()
    detailB.resolve({ data: { id: 'workflow-b', name: 'workflow-b', icon: '', account_avatar: '' } })
    await flushPromises()
    graphB.resolve({ data: { nodes: [{ id: 'node-b', type: 'start' }], edges: [] } })
    await flushPromises()
    graphA.resolve({ data: { nodes: [{ id: 'node-a', type: 'start' }], edges: [] } })
    await flushPromises()

    expect(wrapper.text()).toContain('workflow-b')
    expect(wrapper.get('[data-testid="preview-graph"]').text()).toContain('node-b')
    expect(wrapper.get('[data-testid="preview-graph"]').text()).not.toContain('node-a')
    wrapper.unmount()
  })
})
