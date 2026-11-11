import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import DebugModal from '@/views/space/workflows/components/DebugModal.vue'

const mocks = vi.hoisted(() => ({
  handleDebugWorkflow: vi.fn(),
  cancelDebugWorkflow: vi.fn(),
  canvas: { nodes: [] as any[], edges: [] as any[] },
}))

vi.mock('@vue-flow/core', () => ({
  useVueFlow: () => ({
    nodes: {
      get value() {
        return mocks.canvas.nodes
      },
    },
    edges: {
      get value() {
        return mocks.canvas.edges
      },
    },
  }),
}))
vi.mock('@/hooks/use-workflow', async () => {
  const { ref } = await import('vue')
  return {
    useDebugWorkflow: () => ({
      error: ref(''),
      loading: ref(false),
      handleDebugWorkflow: mocks.handleDebugWorkflow,
      cancelDebugWorkflow: mocks.cancelDebugWorkflow,
    }),
  }
})

const startNode = (id: string) => ({
  node_data: { id, node_type: 'tool', title: id },
  status: 'succeeded',
  outputs: { result: id },
  latency: 0.1,
})

beforeEach(() => {
  mocks.handleDebugWorkflow.mockReset()
  mocks.cancelDebugWorkflow.mockReset()
  mocks.canvas.nodes = [{ id: 'node-a' }, { id: 'node-b' }]
  mocks.canvas.edges = [{ source: 'node-a', target: 'node-b' }]
})

it('isolates results and canvas markers when workflow_id changes during a run', async () => {
  let emitEvent!: (event: Record<string, unknown>) => void
  let finishRun!: () => void
  mocks.handleDebugWorkflow.mockImplementation((_id, _inputs, onData) => {
    emitEvent = onData
    return new Promise<void>((resolve) => {
      finishRun = resolve
    })
  })
  const wrapper = mount(DebugModal, { props: { visible: true, workflow_id: 'workflow-a' } })
  const state = (wrapper.vm as any).$.setupState
  await wrapper.find('a-form').trigger('submit')
  await flushPromises()
  emitEvent({ event: 'workflow', data: startNode('node-a') })
  emitEvent({ event: 'workflow', data: startNode('node-b') })
  emitEvent({ event: 'error', data: { observation: 'workflow A failed' } })

  await wrapper.setProps({ workflow_id: 'workflow-b' })
  expect(mocks.cancelDebugWorkflow).toHaveBeenCalledOnce()
  expect(state.nodeResults).toEqual([])
  emitEvent({ event: 'workflow', data: startNode('node-a') })
  await flushPromises()

  expect(state.nodeResults).toEqual([])
  expect(state.debugWorkflowError).toBe('')
  expect(mocks.canvas.nodes.map(({ class: value }) => value)).toEqual([undefined, undefined])
  expect(mocks.canvas.edges[0].class).toBeUndefined()
  expect(wrapper.findAll('[data-testid="workflow-node-result"]')).toHaveLength(0)
  finishRun()
  await flushPromises()
  wrapper.unmount()
})

it('invalidates an SSE callback immediately when the modal closes', async () => {
  let emitEvent!: (event: Record<string, unknown>) => void
  let finishRun!: () => void
  mocks.handleDebugWorkflow.mockImplementation((_id, _inputs, onData) => {
    emitEvent = onData
    return new Promise<void>((resolve) => {
      finishRun = resolve
    })
  })
  const wrapper = mount(DebugModal, { props: { visible: true, workflow_id: 'workflow-a' } })
  const state = (wrapper.vm as any).$.setupState
  await wrapper.find('a-form').trigger('submit')
  await flushPromises()

  await wrapper.setProps({ visible: false })
  emitEvent({ event: 'workflow', data: startNode('node-a') })
  await flushPromises()

  expect(mocks.cancelDebugWorkflow).toHaveBeenCalledOnce()
  expect(state.nodeResults).toEqual([])
  finishRun()
  await flushPromises()
  wrapper.unmount()
})
