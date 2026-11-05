import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGetWorkflow } from '@/hooks/use-workflow'

const mocks = vi.hoisted(() => ({ getWorkflow: vi.fn() }))
vi.mock('@/services/workflow', () => ({ getWorkflow: (...args: unknown[]) => mocks.getWorkflow(...args) }))
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
