import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Modal } from '@arco-design/web-vue'
import { createRequestError } from '@/utils/error'
import {
  useDebugWorkflow,
  useDeleteWorkflow,
  useGenerateIconPreview,
  useGetPublicWorkflows,
  useGetWorkflowsWithPage,
  useRegenerateIcon,
  useUpdateDraftGraph,
} from '@/hooks/use-workflow'

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

describe('use-workflow request hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls the workflow delete callback only after deletion succeeds', async () => {
    mocks.deleteWorkflow.mockResolvedValueOnce({ message: 'deleted' })
    const callback = vi.fn()
    const { handleDeleteWorkflow } = useDeleteWorkflow()

    handleDeleteWorkflow('workflow-1', callback)
    const onOk = vi.mocked(Modal.warning).mock.calls[0][0].onOk as () => Promise<void>
    await onOk()

    expect(callback).toHaveBeenCalledOnce()
    expect(messageSuccessMock).toHaveBeenCalledWith('deleted')

    callback.mockClear()
    messageSuccessMock.mockClear()
    const requestError = new Error('delete failed')
    mocks.deleteWorkflow.mockRejectedValueOnce(requestError)

    await expect(onOk()).rejects.toBe(requestError)
    expect(callback).not.toHaveBeenCalled()
    expect(messageSuccessMock).not.toHaveBeenCalled()
    expect(messageErrorMock).toHaveBeenCalled()
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

  it('suppresses stale workflow icon error notifications when the caller owns feedback', async () => {
    mocks.generateIconPreview.mockRejectedValueOnce(new Error('generation failed'))
    mocks.regenerateIcon.mockRejectedValueOnce(new Error('regeneration failed'))
    const { handleGenerateIconPreview } = useGenerateIconPreview()
    const { handleRegenerateIcon } = useRegenerateIcon()

    await expect(handleGenerateIconPreview('workflow', '', () => false)).rejects.toThrow('generation failed')
    await expect(handleRegenerateIcon('workflow-1', () => false)).rejects.toThrow('regeneration failed')

    expect(messageErrorMock).not.toHaveBeenCalled()
  })

  it('aborts the active debug request and clears loading when canceled', async () => {
    let signal: AbortSignal
    mocks.debugWorkflow.mockImplementationOnce((_id, _inputs, _onData, requestSignal) =>
      new Promise<void>((_resolve, reject) => {
        signal = requestSignal
        requestSignal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
      }))
    const { loading, handleDebugWorkflow, cancelDebugWorkflow } = useDebugWorkflow(
      () => 'Workflow debug failed',
    )
    const pending = handleDebugWorkflow('workflow-1', {}, () => {})
    cancelDebugWorkflow()

    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    expect(signal!.aborted).toBe(true)
    expect(loading.value).toBe(false)
  })

  it('uses the current localized fallback for a non-string debug response message', async () => {
    mocks.debugWorkflow.mockResolvedValueOnce({ message: null })
    const getFallbackErrorMessage = vi.fn(() => 'Workflow debug failed')
    const { error, handleDebugWorkflow } = useDebugWorkflow(getFallbackErrorMessage)

    await handleDebugWorkflow('workflow-1', {}, () => {})

    expect(getFallbackErrorMessage).toHaveBeenCalledOnce()
    expect(error.value).toBe('Workflow debug failed')
  })

  it.each([
    ['no message field', {}],
    ['an empty message', { message: '' }],
    ['a blank message', { message: '   ' }],
  ])('uses the localized fallback when a non-stream response has %s', async (_case, response) => {
    mocks.debugWorkflow.mockResolvedValueOnce(response)
    const getFallbackErrorMessage = vi.fn(() => 'Workflow debug failed')
    const { error, handleDebugWorkflow } = useDebugWorkflow(getFallbackErrorMessage)

    await handleDebugWorkflow('workflow-1', {}, () => {})

    expect(getFallbackErrorMessage).toHaveBeenCalledOnce()
    expect(error.value).toBe('Workflow debug failed')
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

  it('ignores a stale workflow search error after a newer search succeeds', async () => {
    let rejectOlder!: (error: Error) => void
    const olderResponse = new Promise<WorkflowPageResponse>((_, reject) => { rejectOlder = reject })
    const newerResponse = createDeferred<WorkflowPageResponse>()
    mocks.getWorkflowsWithPage
      .mockReturnValueOnce(olderResponse)
      .mockReturnValueOnce(newerResponse.promise)

    const { loading, workflows, loadWorkflows } = useGetWorkflowsWithPage()
    const olderRequest = loadWorkflows('old', '', true)
    const newerRequest = loadWorkflows('new', '', true)
    newerResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'new-result' }],
      },
    })
    await newerRequest
    rejectOlder(new Error('stale workflow search failed'))

    await expect(olderRequest).resolves.toBeUndefined()
    expect(workflows.value).toEqual([{ id: 'new-result' }])
    expect(loading.value).toBe(false)
  })

  it('propagates the latest workflow search error and resets loading', async () => {
    const requestError = new Error('current workflow search failed')
    mocks.getWorkflowsWithPage.mockRejectedValueOnce(requestError)

    const { loading, loadWorkflows } = useGetWorkflowsWithPage()

    await expect(loadWorkflows('current', '', true)).rejects.toBe(requestError)
    expect(loading.value).toBe(false)
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

  it('does not invalidate in-flight initial load when concurrent scroll triggers pagination', async () => {
    const initialResponse = createDeferred<WorkflowPageResponse>()
    mocks.getWorkflowsWithPage.mockReturnValueOnce(initialResponse.promise)

    const { loading, workflows, paginator, loadWorkflows } = useGetWorkflowsWithPage()

    const initialRequest = loadWorkflows('', '', true)
    expect(loading.value).toBe(true)

    const scrollRequest = loadWorkflows('', '', false)
    await scrollRequest

    expect(mocks.getWorkflowsWithPage).toHaveBeenCalledTimes(1)
    expect(loading.value).toBe(true)

    initialResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 2, total_record: 25 },
        list: [{ id: 'wf-1' }],
      },
    })
    await initialRequest

    expect(workflows.value).toEqual([{ id: 'wf-1' }])
    expect(paginator.value.current_page).toBe(2)
    expect(loading.value).toBe(false)
  })

  it('does not increment generation or alter loading when pagination is called without more pages', async () => {
    const { loading, paginator, loadWorkflows } = useGetWorkflowsWithPage()
    paginator.value = { current_page: 3, page_size: 20, total_page: 2, total_record: 25 }

    await loadWorkflows('', '', false)

    expect(mocks.getWorkflowsWithPage).not.toHaveBeenCalled()
    expect(loading.value).toBe(false)
  })

  describe('useGetPublicWorkflows', () => {
    it('loads public workflows successfully', async () => {
      mocks.getWorkflowsWithPage.mockResolvedValueOnce({
        data: { list: [{ id: 'wf-public-1' }] },
      })

      const { loading, workflows, loadPublicWorkflows } = useGetPublicWorkflows()
      await loadPublicWorkflows('test')

      expect(workflows.value).toEqual([{ id: 'wf-public-1' }])
      expect(loading.value).toBe(false)
    })

    it('ignores stale search results and keeps loading true until the newest request resolves', async () => {
      const older = createDeferred<{ data: { list: { id: string }[] } }>()
      const newer = createDeferred<{ data: { list: { id: string }[] } }>()
      mocks.getWorkflowsWithPage
        .mockReturnValueOnce(older.promise)
        .mockReturnValueOnce(newer.promise)

      const { loading, workflows, loadPublicWorkflows } = useGetPublicWorkflows()
      const req1 = loadPublicWorkflows('first')
      const req2 = loadPublicWorkflows('second')

      expect(loading.value).toBe(true)

      older.resolve({ data: { list: [{ id: 'wf-first' }] } })
      await req1

      expect(workflows.value).toEqual([])
      expect(loading.value).toBe(true)

      newer.resolve({ data: { list: [{ id: 'wf-second' }] } })
      await req2

      expect(workflows.value).toEqual([{ id: 'wf-second' }])
      expect(loading.value).toBe(false)
    })
  })
})
