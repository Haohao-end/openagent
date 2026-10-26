import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DebugModal from '@/views/space/workflows/components/DebugModal.vue'
import { copyTextToClipboard } from '@/utils/clipboard'

vi.mock('@/utils/clipboard', () => ({
  copyTextToClipboard: vi.fn().mockResolvedValue(undefined),
}))

const mocks = vi.hoisted(() => ({
  handleDebugWorkflow: vi.fn(),
  canvas: {
    nodes: [] as { id: string; class?: string | string[] }[],
    edges: [] as { source: string; target: string; sourceHandle?: string; class?: string | string[] }[],
  },
}))

vi.mock('@vue-flow/core', () => ({
  useVueFlow: () => ({
    nodes: { get value() { return mocks.canvas.nodes } },
    edges: { get value() { return mocks.canvas.edges } },
  }),
}))

vi.mock('@/hooks/use-workflow', async () => {
  const { ref } = await import('vue')

  return {
    useDebugWorkflow: () => ({
      error: ref(''),
      loading: ref(false),
      handleDebugWorkflow: mocks.handleDebugWorkflow,
    }),
  }
})

const nodeResults = [
  {
    node_data: { id: 'start-1', node_type: 'start', type: 'start', title: 'Start' },
    status: 'succeeded',
    outputs: { query: 'weather' },
    latency: 0.1,
  },
  {
    node_data: { id: 'condition-1', node_type: 'if_else', type: 'if_else', title: 'Condition' },
    status: 'succeeded',
    outputs: { result: true },
    latency: 0.05,
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
      { id: 'condition-1' },
      { id: 'tool-1' },
      { id: 'tool-2' },
      { id: 'end-1' },
    ]
    mocks.canvas.edges = [
      { source: 'start-1', target: 'condition-1' },
      { source: 'condition-1', target: 'tool-1', sourceHandle: 'true' },
      { source: 'condition-1', target: 'tool-2', sourceHandle: 'false' },
      { source: 'tool-1', target: 'end-1' },
      { source: 'tool-2', target: 'end-1' },
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
    expect(resultRows).toHaveLength(4)
    expect(resultRows.map((row) => row.text())).toEqual([
      expect.stringContaining('Start'),
      expect.stringContaining('Condition'),
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
      undefined,
      ['workflow-debug-succeeded'],
    ])
    expect(mocks.canvas.edges.map(({ class: className }) => className)).toEqual([
      ['workflow-debug-edge-succeeded'],
      ['workflow-debug-edge-succeeded'],
      undefined,
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
      undefined,
      undefined,
    ])
    expect(mocks.canvas.edges.every(({ class: className }) => !className)).toBe(true)
  })

  it('renders detailed error text for a failed node', async () => {
    mocks.handleDebugWorkflow.mockImplementationOnce(async (_workflowId, _inputs, onData) => {
      onData({
        event: 'workflow',
        data: {
          node_data: { node_type: 'tool', type: 'tool', title: 'Weather' },
          status: 'failed',
          error: 'Weather provider returned HTTP 503',
          outputs: {},
          latency: 0.2,
        },
      })
    })

    const wrapper = mount(DebugModal, {
      props: { visible: true, workflow_id: 'workflow-1' },
    })

    await wrapper.find('a-form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-node-error"]').text()).toContain(
      'Weather provider returned HTTP 503',
    )
  })

  it.each([
    ['error', 'Workflow execution failed at node Weather'],
    ['timeout', 'Workflow execution timed out at node Weather'],
  ])('shows %s stream failures without treating them as node results', async (event, detail) => {
    mocks.handleDebugWorkflow.mockImplementationOnce(async (_workflowId, _inputs, onData) => {
      onData({
        event,
        data: { event, observation: detail },
      })
    })

    const wrapper = mount(DebugModal, {
      props: { visible: true, workflow_id: 'workflow-1' },
    })

    await wrapper.find('a-form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain(detail)
    expect(wrapper.findAll('[data-testid="workflow-node-result"]')).toHaveLength(0)
  })

  it('clears old execution markers when the debug modal is reopened', async () => {
    const wrapper = mount(DebugModal, {
      props: { visible: false, workflow_id: 'workflow-1' },
    })

    await wrapper.setProps({ visible: true })
    await wrapper.find('a-form').trigger('submit')
    await flushPromises()
    expect(mocks.canvas.nodes[0].class).toContain('workflow-debug-succeeded')

    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(mocks.canvas.nodes.map(({ class: className }) => className)).toEqual([
      ['custom-node'],
      undefined,
      undefined,
      undefined,
      undefined,
    ])
    expect(mocks.canvas.edges.every(({ class: className }) => !className)).toBe(true)
    expect(wrapper.findAll('[data-testid="workflow-node-result"]')).toHaveLength(0)
  })

  it('shows request errors in the output panel', async () => {
    mocks.handleDebugWorkflow.mockRejectedValueOnce(new Error('network disconnected'))

    const wrapper = mount(DebugModal, {
      props: { visible: true, workflow_id: 'workflow-1' },
    })

    await wrapper.find('a-form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('network disconnected')
  })


  it('copies failed node error details for sharing with support or an assistant', async () => {
    vi.mocked(copyTextToClipboard).mockResolvedValueOnce(undefined)
    mocks.handleDebugWorkflow.mockImplementationOnce(async (_workflowId, _inputs, onData) => {
      onData({
        event: 'workflow',
        data: {
          node_data: { node_type: 'tool', type: 'tool', title: 'Weather' },
          status: 'failed',
          error: 'Weather provider returned HTTP 503',
          outputs: {},
          latency: 0.2,
        },
      })
    })

    const wrapper = mount(DebugModal, {
      props: { visible: true, workflow_id: 'workflow-1' },
    })

    await wrapper.find('a-form').trigger('submit')
    await flushPromises()
    await wrapper.find('[data-testid="copy-node-error"]').trigger('click')
    await flushPromises()

    expect(copyTextToClipboard).toHaveBeenCalledWith('Weather provider returned HTTP 503')
  })
})
