import { describe, expect, it } from 'vitest'
import type { WorkflowResultTraceStep } from '@/models/workflow'

describe('WorkflowResultTraceStep structure', () => {
  it('should match the expected node_data serialization format', () => {
    const step: WorkflowResultTraceStep = {
      id: 'step-1',
      node_data: {
        id: 'node-1',
        node_type: 'llm',
        title: 'LLM Node',
        inputs: { prompt: 'hello' },
        outputs: { text: 'world' },
      },
      status: 'completed',
      latency: 0.5,
      created_at: 1700000000,
    }

    expect(step.node_data.id).toBe('node-1')
    expect(step.node_data.node_type).toBe('llm')
    expect(step.node_data.inputs?.prompt).toBe('hello')
  })
})
