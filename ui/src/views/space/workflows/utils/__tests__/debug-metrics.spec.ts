import { describe, expect, it } from 'vitest'
import {
  formatDebugNodeOutputs,
  findWorkflowOutputs,
  sumWorkflowLatency,
  sumWorkflowToolLatency,
  type DebugNodeResult,
} from '@/views/space/workflows/utils/debug-metrics'

const mockNodeResults: DebugNodeResult[] = [
  {
    node_data: {
      node_type: 'start',
      type: 'start',
      title: '开始',
    },
    outputs: null,
    latency: 0.12,
  },
  {
    node_data: {
      node_type: 'tool',
      title: '工具节点',
    },
    outputs: { query: 'weather' },
    latency: 0.35,
  },
  {
    node_data: {
      node_type: 'end',
      type: 'end',
      title: '结束',
    },
    outputs: { text: 'done' },
    latency: 0.18,
  },
]

describe('debug-metrics', () => {
  it('formats structured node outputs for display', () => {
    expect(formatDebugNodeOutputs({ query: 'weather', count: 2 })).toBe(`{
  "query": "weather",
  "count": 2
}`)
  })

  it('shows missing node output as unavailable instead of the word undefined', () => {
    expect(formatDebugNodeOutputs(undefined)).toBe('—')
    expect(formatDebugNodeOutputs(null)).toBe('null')
    expect(formatDebugNodeOutputs('')).toBe('')
  })

  it('keeps text node outputs readable without JSON quoting', () => {
    expect(formatDebugNodeOutputs('Sunny, 22°C')).toBe('Sunny, 22°C')
  })

  it('returns end node outputs', () => {
    expect(findWorkflowOutputs(mockNodeResults)).toEqual({ text: 'done' })
  })

  it('ignores malformed node metadata while retaining valid end and tool results', () => {
    const withMissingNode = [
      { node_data: null, outputs: null, latency: 1 } as unknown as DebugNodeResult,
      { node_data: { node_type: 'tool' }, outputs: {}, latency: 0.2 },
      { node_data: { node_type: 'end' }, outputs: { answer: 'OK' }, latency: 0.1 },
    ]

    expect(findWorkflowOutputs(withMissingNode)).toEqual({ answer: 'OK' })
    expect(sumWorkflowToolLatency(withMissingNode)).toBeCloseTo(0.2)
  })

  it('uses the latest completed end-node event instead of a stale earlier output', () => {
    const updates: DebugNodeResult[] = [
      { node_data: { node_type: 'end' }, outputs: { answer: 'partial' }, latency: 0.1 },
      { node_data: { node_type: 'tool' }, outputs: {}, latency: 0.1 },
      { node_data: { node_type: 'end' }, outputs: { answer: 'complete' }, latency: 0.2 },
    ]
    expect(findWorkflowOutputs(updates)).toEqual({ answer: 'complete' })
  })

  it('uses the legacy node type when end nodes omit node_type', () => {
    const events: DebugNodeResult[] = [
      { node_data: { type: 'end' }, outputs: { answer: 'legacy' }, latency: 0.2 },
    ]
    expect(findWorkflowOutputs(events)).toEqual({ answer: 'legacy' })
  })

  it('returns null when end node is missing', () => {
    const withoutEnd = mockNodeResults.filter((item) => item.node_data.node_type !== 'end')
    expect(findWorkflowOutputs(withoutEnd)).toBeNull()
  })

  it('ignores malformed and negative latencies without corrupting metrics', () => {
    const broken: DebugNodeResult[] = [
      { node_data: { node_type: 'tool' }, outputs: null, latency: Number.NaN },
      { node_data: { node_type: 'tool' }, outputs: null, latency: -12 },
      { node_data: { node_type: 'tool' }, outputs: null, latency: Number.POSITIVE_INFINITY },
      { node_data: { node_type: 'tool' }, outputs: null, latency: 0.25 },
      { node_data: { type: 'start' }, outputs: null, latency: 0.1 },
    ]

    expect(sumWorkflowLatency(broken)).toBeCloseTo(0.35)
    expect(sumWorkflowToolLatency(broken)).toBeCloseTo(0.25)
  })

  it('sums all node latency', () => {
    expect(sumWorkflowLatency(mockNodeResults)).toBeCloseTo(0.65)
  })

  it('sums only tool node latency', () => {
    expect(sumWorkflowToolLatency(mockNodeResults)).toBeCloseTo(0.35)
  })
})
