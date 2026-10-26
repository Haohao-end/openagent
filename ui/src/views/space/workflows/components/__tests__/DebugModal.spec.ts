import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DebugModal from '@/views/space/workflows/components/DebugModal.vue'

const mocks = vi.hoisted(() => ({
  handleDebugWorkflow: vi.fn(),
}))

vi.mock('@vue-flow/core', () => ({
  useVueFlow: () => ({ nodes: { value: [] } }),
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
    node_data: { node_type: 'start', type: 'start', title: 'Start' },
    outputs: { query: 'weather' },
    latency: 0.1,
  },
  {
    node_data: { node_type: 'tool', type: 'tool', title: 'Weather' },
    outputs: { temperature: 22 },
    latency: 0.2,
  },
  {
    node_data: { node_type: 'end', type: 'end', title: 'End' },
    outputs: { answer: 'Sunny' },
    latency: 0.1,
  },
]

describe('DebugModal node outputs', () => {
  beforeEach(() => {
    mocks.handleDebugWorkflow.mockReset()
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
  })
})
