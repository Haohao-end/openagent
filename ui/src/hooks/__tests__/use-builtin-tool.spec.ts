import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGetBuiltinTool } from '@/hooks/use-builtin-tool'

const mocks = vi.hoisted(() => ({ getBuiltinTool: vi.fn() }))

vi.mock('@/services/builtin-tool', () => ({
  getBuiltinTool: (...args: unknown[]) => mocks.getBuiltinTool(...args),
  getBuiltinTools: vi.fn(),
  getCategories: vi.fn(),
}))

describe('useGetBuiltinTool', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps the latest tool details when requests resolve out of order', async () => {
    const defer = () => {
      let resolve!: (value: any) => void
      const promise = new Promise<any>((done) => { resolve = done })
      return { promise, resolve }
    }
    const oldRequest = defer()
    const newRequest = defer()
    mocks.getBuiltinTool.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)
    const { builtin_tool, loading, loadBuiltinTool } = useGetBuiltinTool()

    const oldLoad = loadBuiltinTool('provider', 'old')
    const newLoad = loadBuiltinTool('provider', 'new')
    newRequest.resolve({ data: { inputs: [{ name: 'new' }], params: [] } })
    await newLoad

    oldRequest.resolve({ data: { inputs: [{ name: 'old' }], params: [] } })
    const oldResult = await oldLoad
    expect(builtin_tool.value.inputs).toEqual([{ name: 'new' }])
    expect(oldResult).toBe(false)
    expect(loading.value).toBe(false)
  })
})
