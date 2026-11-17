import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGetDraftGraph, useGetWorkflow } from '@/hooks/use-workflow'

const mocks = vi.hoisted(() => ({
  getWorkflow: vi.fn(),
  getDraftGraph: vi.fn(),
}))
vi.mock('@/services/workflow', () => ({
  getWorkflow: (...args: unknown[]) => mocks.getWorkflow(...args),
  getDraftGraph: (...args: unknown[]) => mocks.getDraftGraph(...args),
}))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn(), error: vi.fn() }, Modal: { warning: vi.fn() } }))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('useGetWorkflow', () => {
  beforeEach(() => mocks.getWorkflow.mockReset())

  it('ignores a detail response that resolves after a newer refresh', async () => {
    const older = deferred<{ data: { name: string; is_debug_passed: boolean } }>()
    const newer = deferred<{ data: { name: string; is_debug_passed: boolean } }>()
    mocks.getWorkflow.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    const { workflow, loadWorkflow } = useGetWorkflow()
    const oldRequest = loadWorkflow('workflow-1')
    const newRequest = loadWorkflow('workflow-1')
    newer.resolve({ data: { name: 'current', is_debug_passed: true } })
    await newRequest
    older.resolve({ data: { name: 'stale', is_debug_passed: false } })
    await oldRequest
    expect(workflow.value).toMatchObject({ name: 'current', is_debug_passed: true })
  })
})

describe('useGetDraftGraph', () => {
  beforeEach(() => mocks.getDraftGraph.mockReset())

  it('ignores a draft graph response that resolves after a newer request', async () => {
    const older = deferred<{ data: { nodes: any[]; edges: any[] } }>()
    const newer = deferred<{ data: { nodes: any[]; edges: any[] } }>()
    mocks.getDraftGraph.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    const { nodes, loading, loadDraftGraph } = useGetDraftGraph()

    const oldRequest = loadDraftGraph('workflow-1')
    const newRequest = loadDraftGraph('workflow-2')

    expect(loading.value).toBe(true)

    newer.resolve({
      data: {
        nodes: [{ id: 'node-new', node_type: 'llm', position: { x: 0, y: 0 } }],
        edges: [],
      },
    })
    await newRequest

    older.resolve({
      data: {
        nodes: [{ id: 'node-old', node_type: 'tool', position: { x: 10, y: 10 } }],
        edges: [],
      },
    })
    await oldRequest

    expect(nodes.value).toMatchObject([{ id: 'node-new', type: 'llm' }])
    expect(loading.value).toBe(false)
  })
})
