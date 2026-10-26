import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DebugModal from '@/views/space/workflows/components/DebugModal.vue'

const mocks = vi.hoisted(() => ({
  handleDebugWorkflow: vi.fn(),
  canvas: { nodes: [] as { id: string; class?: string | string[] }[], edges: [] as { source: string; target: string; class?: string | string[] }[] },
}))

vi.mock('@vue-flow/core', () => ({
  useVueFlow: () => ({
    nodes: { get value() { return mocks.canvas.nodes } },
    edges: { get value() { return mocks.canvas.edges } },
  }),
}))

vi.mock('@/hooks/use-workflow', () => ({
  useDebugWorkflow: () => ({
    error: { value: '' },
    loading: { value: false },
    handleDebugWorkflow: mocks.handleDebugWorkflow,
  }),
}))

const nodeResults = [
  {
    node_data: { id: 'start-1', node_type: 'start', type: 'start', title: 'Start' },
    status: 'succeeded',
    outputs: { query: 'weather' },
    latency: 0.1,
  },
  {
    node_data: { id: 'tool-1', node_type: 'tool', type: 'tool', title: 'Weather' },
    status: 'succeeded',
    outputs: { temperature: 22 },
    latency: 0.2,
  },
  {
    node_data: { id: 'end-1', node_type: 'end', type: 'end', title: 'End' },
    status: 'succeeded',
    outputs: { answer: 'Sunny' },
    latency: 0.1,
  },
]

describe('DebugModal node outputs', () => {
  beforeEach(() => {
    mocks.handleDebugWorkflow.mockReset()
    mocks.canvas.nodes = [
      { id: 'start-1', class: 'custom-node' },
      { id: 'tool-1' },
      { id: 'end-1' },
    ]
    mocks.canvas.edges = [
      { source: 'start-1', target: 'tool-1' },
      { source: 'tool-1', target: 'end-1' },
      { source: 'start-1', target: 'end-1' },
    ]
    mocks.handleDebugWorkflow.mockImplementation(async (_workflowId, _inputs, onData) => {
      nodeResults.forEach((data) => onData({ data }))
    })
  })

  it('renders outputs for every node received from the workflow debug stream', async () => {
    const wrapper = mount(DebugModal, {
      props: { visible: true, workflow_id: 'workflow-1' },
    })

    await wrapper.find('a-form').trigger('submit')
    await flushPromises()

    const resultRows = wrapper.findAll('[data-testid="workflow-node-result"]')
    expect(resultRows).toHaveLength(3)
    expect(resultRows.map((row) => row.text())).toEqual([
      expect.stringContaining('Start'),
      expect.stringContaining('Weather'),
      expect.stringContaining('End'),
    ])
    expect(wrapper.text()).toContain('"temperature": 22')
    expect(wrapper.text()).toContain('"answer": "Sunny"')
    expect(mocks.handleDebugWorkflow).toHaveBeenCalledOnce()
    expect(mocks.canvas.nodes.map(({ class: className }) => className)).toEqual([
      ['custom-node', 'workflow-debug-succeeded'],
      ['workflow-debug-succeeded'],
      ['workflow-debug-succeeded'],
    ])
    expect(mocks.canvas.edges.map(({ class: className }) => className)).toEqual([
      ['workflow-debug-edge-succeeded'],
      ['workflow-debug-edge-succeeded'],
      undefined,
    ])
  })

  it('clears prior node and edge markers before a new debug run', async () => {
    const wrapper = mount(DebugModal, {
      props: { visible: true, workflow_id: 'workflow-1' },
    })

    await wrapper.find('a-form').trigger('submit')
    await flushPromises()
    expect(mocks.canvas.nodes[0].class).toContain('workflow-debug-succeeded')

    mocks.handleDebugWorkflow.mockImplementationOnce(async () => undefined)
    await wrapper.find('a-form').trigger('submit')
    await flushPromises()

    expect(mocks.canvas.nodes.map(({ class: className }) => className)).toEqual([
      ['custom-node'],
      undefined,
      undefined,
    ])
    expect(mocks.canvas.edges.every(({ class: className }) => !className)).toBe(true)
  })
})
