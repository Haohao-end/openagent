import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGetWorkflowResultTrace } from '@/hooks/use-workflow'
import * as workflowService from '@/services/workflow'

vi.mock('@/services/workflow', () => ({
  cancelPublishWorkflow: vi.fn(),
  createWorkflow: vi.fn(),
  debugWorkflow: vi.fn(),
  deleteWorkflow: vi.fn(),
  generateIconPreview: vi.fn(),
  getDraftGraph: vi.fn(),
  getWorkflow: vi.fn(),
  getWorkflowResultTrace: vi.fn(),
  getWorkflowsWithPage: vi.fn(),
  publishWorkflow: vi.fn(),
  regenerateIcon: vi.fn(),
  shareWorkflow: vi.fn(),
  updateDraftGraph: vi.fn(),
  updateWorkflow: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

describe('useGetWorkflowResultTrace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads workflow result trace and updates state upon success', async () => {
    const mockTrace = {
      id: 'res-1',
      workflow_id: 'wf-1',
      status: 'succeeded',
      latency: 0.95,
      created_at: 1700000000,
      updated_at: 1700000001,
      steps: [{ node_id: 'start_1', status: 'completed' }],
    }
    vi.mocked(workflowService.getWorkflowResultTrace).mockResolvedValue({
      code: 'success',
      data: mockTrace,
    } as never)

    const { loading, trace, loadWorkflowResultTrace } = useGetWorkflowResultTrace()
    expect(loading.value).toBe(false)
    expect(trace.value).toBeNull()

    const promise = loadWorkflowResultTrace('wf-1', 'res-1')
    expect(loading.value).toBe(true)
    const result = await promise

    expect(result).toEqual(mockTrace)
    expect(trace.value).toEqual(mockTrace)
    expect(loading.value).toBe(false)
  })

  it('guards against race conditions when a slower request resolves after a newer request', async () => {
    let resolveFirst!: (value: any) => void
    let resolveSecond!: (value: any) => void

    const p1 = new Promise((resolve) => { resolveFirst = resolve })
    const p2 = new Promise((resolve) => { resolveSecond = resolve })

    vi.mocked(workflowService.getWorkflowResultTrace)
      .mockImplementationOnce(() => p1 as any)
      .mockImplementationOnce(() => p2 as any)

    const { loading, trace, loadWorkflowResultTrace } = useGetWorkflowResultTrace()

    const call1 = loadWorkflowResultTrace('wf-1', 'res-1')
    const call2 = loadWorkflowResultTrace('wf-1', 'res-2')

    resolveSecond({
      code: 'success',
      data: { id: 'res-2', workflow_id: 'wf-1', status: 'succeeded', steps: [] },
    })
    await call2

    expect(trace.value?.id).toBe('res-2')

    resolveFirst({
      code: 'success',
      data: { id: 'res-1', workflow_id: 'wf-1', status: 'succeeded', steps: [] },
    })
    await call1

    expect(trace.value?.id).toBe('res-2')
    expect(loading.value).toBe(false)
  })

  it('clears trace state and resets loading immediately', async () => {
    let resolvePending!: (value: any) => void
    const pendingPromise = new Promise((resolve) => { resolvePending = resolve })
    vi.mocked(workflowService.getWorkflowResultTrace).mockImplementation(() => pendingPromise as any)

    const { loading, trace, loadWorkflowResultTrace, clearWorkflowResultTrace } =
      useGetWorkflowResultTrace()

    loadWorkflowResultTrace('wf-1', 'res-pending')
    expect(loading.value).toBe(true)

    clearWorkflowResultTrace()
    expect(loading.value).toBe(false)
    expect(trace.value).toBeNull()

    resolvePending({
      code: 'success',
      data: { id: 'res-pending', steps: [] },
    })
    await new Promise((r) => setTimeout(r, 0))

    expect(trace.value).toBeNull()
  })
})
