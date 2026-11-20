import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Message } from '@arco-design/web-vue'
import { useCreateWorkflow, useUpdateWorkflow } from '@/hooks/use-workflow'

const mocks = vi.hoisted(() => ({
  createWorkflow: vi.fn(),
  updateWorkflow: vi.fn(),
  routerPush: vi.fn(),
}))

vi.mock('@/services/workflow', () => ({
  createWorkflow: (...args: unknown[]) => mocks.createWorkflow(...args),
  updateWorkflow: (...args: unknown[]) => mocks.updateWorkflow(...args),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.routerPush }) }))
vi.mock('@arco-design/web-vue', () => ({
  Message: { success: vi.fn(), error: vi.fn() },
  Modal: { warning: vi.fn() },
}))

describe('useCreateWorkflow and useUpdateWorkflow mutations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('skips navigation when the creating modal session has ended', async () => {
    mocks.createWorkflow.mockResolvedValue({ data: { id: 'workflow-1' } })
    const { handleCreateWorkflow } = useCreateWorkflow()

    await handleCreateWorkflow({ tool_call_name: 'workflow' } as any, () => false)

    expect(mocks.createWorkflow).toHaveBeenCalledOnce()
    expect(mocks.routerPush).not.toHaveBeenCalled()
  })

  it('drops stale creation response when a newer request is in flight', async () => {
    let resolve1!: (val: any) => void
    let resolve2!: (val: any) => void
    const p1 = new Promise((r) => { resolve1 = r })
    const p2 = new Promise((r) => { resolve2 = r })

    mocks.createWorkflow.mockReturnValueOnce(p1).mockReturnValueOnce(p2)

    const { handleCreateWorkflow, loading } = useCreateWorkflow()

    const req1 = handleCreateWorkflow({ tool_call_name: 'workflow_first' } as any)
    const req2 = handleCreateWorkflow({ tool_call_name: 'workflow_second' } as any)
    expect(loading.value).toBe(true)

    resolve2({ data: { id: 'wf-2' } })
    await req2
    expect(mocks.routerPush).toHaveBeenCalledWith({
      name: 'space-workflows-detail',
      params: { workflow_id: 'wf-2' },
    })
    expect(Message.success).toHaveBeenCalledWith('创建工作流成功')
    expect(loading.value).toBe(false)

    resolve1({ data: { id: 'wf-1' } })
    await req1
    expect(mocks.routerPush).not.toHaveBeenCalledWith({
      name: 'space-workflows-detail',
      params: { workflow_id: 'wf-1' },
    })
  })

  it('drops stale update response when a newer request is in flight', async () => {
    let resolve1!: (val: any) => void
    let resolve2!: (val: any) => void
    const p1 = new Promise((r) => { resolve1 = r })
    const p2 = new Promise((r) => { resolve2 = r })

    mocks.updateWorkflow.mockReturnValueOnce(p1).mockReturnValueOnce(p2)

    const { handleUpdateWorkflow, loading } = useUpdateWorkflow()

    const req1 = handleUpdateWorkflow('wf-id', { tool_call_name: 'wf_old' } as any)
    const req2 = handleUpdateWorkflow('wf-id', { tool_call_name: 'wf_new' } as any)
    expect(loading.value).toBe(true)

    resolve2({ message: 'updated new' })
    await req2
    expect(Message.success).toHaveBeenCalledWith('updated new')
    expect(loading.value).toBe(false)

    resolve1({ message: 'updated old' })
    await req1
    expect(Message.success).not.toHaveBeenCalledWith('updated old')
  })
})
