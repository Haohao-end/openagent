import { describe, expect, it } from 'vitest'
import {
  clearWorkflowDebugVisualization,
  markWorkflowDebugEdgeSucceeded,
  markWorkflowDebugNodeSucceeded,
} from '@/views/space/workflows/utils/debug-visualization'

describe('workflow debug visualization', () => {
  it('marks the matching node while preserving its existing classes', () => {
    const nodes = [{ id: 'node-1', class: ['selected', 'custom-node'] }]

    markWorkflowDebugNodeSucceeded(nodes, 'node-1')

    expect(nodes[0].class).toEqual(['selected', 'custom-node', 'workflow-debug-succeeded'])
  })

  it('marks only the edge on an observed transition', () => {
    const edges = [
      { source: 'node-1', target: 'node-2', class: undefined },
      { source: 'node-1', target: 'node-3', class: undefined },
    ]

    markWorkflowDebugEdgeSucceeded(edges, 'node-1', 'node-3')

    expect(edges.map(({ class: className }) => className)).toEqual([
      undefined,
      ['workflow-debug-edge-succeeded'],
    ])
  })

  it('clears debug markers and preserves unrelated classes', () => {
    const nodes = [{ id: 'node-1', class: ['selected', 'workflow-debug-succeeded'] }]
    const edges = [{ source: 'node-1', target: 'node-2', class: 'workflow-debug-edge-succeeded custom-edge' }]

    clearWorkflowDebugVisualization(nodes, edges)

    expect(nodes[0].class).toEqual(['selected'])
    expect(edges[0].class).toEqual(['custom-edge'])
  })
})
