import { expect, it, vi } from 'vitest'
import { useCreateWorkflow } from '@/hooks/use-workflow'

const mocks = vi.hoisted(() => ({ createWorkflow: vi.fn(), routerPush: vi.fn() }))
vi.mock('@/services/workflow', () => ({ createWorkflow: (...args: unknown[]) => mocks.createWorkflow(...args) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.routerPush }) }))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn(), error: vi.fn() }, Modal: { warning: vi.fn() } }))

it('skips navigation when the creating modal session has ended', async () => {
  mocks.createWorkflow.mockResolvedValue({ data: { id: 'workflow-1' } })
  const { handleCreateWorkflow } = useCreateWorkflow()

  await handleCreateWorkflow({ tool_call_name: 'workflow' } as any, () => false)

  expect(mocks.createWorkflow).toHaveBeenCalledOnce()
  expect(mocks.routerPush).not.toHaveBeenCalled()
})
