import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRequestError } from '@/utils/error'
import { useGetWorkflowsWithPage, useUpdateDraftGraph } from '@/hooks/use-workflow'

const mocks = vi.hoisted(() => ({
  cancelPublishWorkflow: vi.fn(),
  createWorkflow: vi.fn(),
  debugWorkflow: vi.fn(),
  deleteWorkflow: vi.fn(),
  generateIconPreview: vi.fn(),
  getDraftGraph: vi.fn(),
  getWorkflow: vi.fn(),
  getWorkflowsWithPage: vi.fn(),
  publishWorkflow: vi.fn(),
  regenerateIcon: vi.fn(),
  shareWorkflow: vi.fn(),
  updateDraftGraph: vi.fn(),
  updateWorkflow: vi.fn(),
}))

const messageSuccessMock = vi.fn()
const messageErrorMock = vi.fn()

type WorkflowPageResponse = {
  data: {
    paginator: { current_page: number; page_size: number; total_page: number; total_record: number }
    list: { id: string }[]
  }
}

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

vi.mock('@/services/workflow', () => ({
  cancelPublishWorkflow: (...args: unknown[]) => mocks.cancelPublishWorkflow(...args),
  createWorkflow: (...args: unknown[]) => mocks.createWorkflow(...args),
  debugWorkflow: (...args: unknown[]) => mocks.debugWorkflow(...args),
  deleteWorkflow: (...args: unknown[]) => mocks.deleteWorkflow(...args),
  generateIconPreview: (...args: unknown[]) => mocks.generateIconPreview(...args),
  getDraftGraph: (...args: unknown[]) => mocks.getDraftGraph(...args),
  getWorkflow: (...args: unknown[]) => mocks.getWorkflow(...args),
  getWorkflowsWithPage: (...args: unknown[]) => mocks.getWorkflowsWithPage(...args),
  publishWorkflow: (...args: unknown[]) => mocks.publishWorkflow(...args),
  regenerateIcon: (...args: unknown[]) => mocks.regenerateIcon(...args),
  shareWorkflow: (...args: unknown[]) => mocks.shareWorkflow(...args),
  updateDraftGraph: (...args: unknown[]) => mocks.updateDraftGraph(...args),
  updateWorkflow: (...args: unknown[]) => mocks.updateWorkflow(...args),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: (message: string) => messageSuccessMock(message),
    error: (message: string) => messageErrorMock(message),
  },
  Modal: {
    warning: vi.fn(),
  },
}))

describe('use-workflow draft save feedback', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns true when draft graph save succeeds without notification', async () => {
    mocks.updateDraftGraph.mockResolvedValue({
      message: '保存成功',
    })

    const { handleUpdateDraftGraph } = useUpdateDraftGraph()
    const result = await handleUpdateDraftGraph(
      'workflow-1',
      { nodes: [], edges: [] } as any,
      false,
    )

    expect(result).toBe(true)
    expect(mocks.updateDraftGraph).toHaveBeenCalledWith('workflow-1', { nodes: [], edges: [] })
    expect(messageSuccessMock).not.toHaveBeenCalled()
    expect(messageErrorMock).not.toHaveBeenCalled()
  })

  it('returns false and shows backend error when draft graph save fails', async () => {
    mocks.updateDraftGraph.mockRejectedValue(
      createRequestError({
        message: 'URL解析到不允许的地址: 169.254.169.254',
      }),
    )

    const { handleUpdateDraftGraph } = useUpdateDraftGraph()
    const result = await handleUpdateDraftGraph(
      'workflow-1',
      { nodes: [], edges: [] } as any,
      false,
    )

    expect(result).toBe(false)
    expect(messageErrorMock).toHaveBeenCalledWith('URL解析到不允许的地址: 169.254.169.254')
    expect(messageSuccessMock).not.toHaveBeenCalled()
  })
})

describe('useGetWorkflowsWithPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores a stale search result after a newer search completes', async () => {
    const olderResponse = createDeferred<WorkflowPageResponse>()
    const newerResponse = createDeferred<WorkflowPageResponse>()
    mocks.getWorkflowsWithPage
      .mockReturnValueOnce(olderResponse.promise)
      .mockReturnValueOnce(newerResponse.promise)

    const { workflows, loadWorkflows } = useGetWorkflowsWithPage()
    const olderRequest = loadWorkflows('old', '', true)
    const newerRequest = loadWorkflows('new', '', true)

    newerResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'new-result' }],
      },
    })
    await newerRequest
    olderResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'old-result' }],
      },
    })
    await olderRequest

    expect(workflows.value).toEqual([{ id: 'new-result' }])
  })

  it('keeps loading while the newest workflow search is pending', async () => {
    const olderResponse = createDeferred<WorkflowPageResponse>()
    const newerResponse = createDeferred<WorkflowPageResponse>()
    mocks.getWorkflowsWithPage
      .mockReturnValueOnce(olderResponse.promise)
      .mockReturnValueOnce(newerResponse.promise)

    const { loading, loadWorkflows } = useGetWorkflowsWithPage()
    const olderRequest = loadWorkflows('old', '', true)
    const newerRequest = loadWorkflows('new', '', true)

    olderResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'old-result' }],
      },
    })
    await olderRequest

    expect(loading.value).toBe(true)

    newerResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'new-result' }],
      },
    })
    await newerRequest

    expect(loading.value).toBe(false)
  })
})
