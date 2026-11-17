import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGetBuiltinTool, useGetBuiltinTools, useGetCategories } from '@/hooks/use-builtin-tool'

const mocks = vi.hoisted(() => ({
  getBuiltinTool: vi.fn(),
  getBuiltinTools: vi.fn(),
  getCategories: vi.fn(),
}))

vi.mock('@/services/builtin-tool', () => ({
  getBuiltinTool: (...args: unknown[]) => mocks.getBuiltinTool(...args),
  getBuiltinTools: (...args: unknown[]) => mocks.getBuiltinTools(...args),
  getCategories: (...args: unknown[]) => mocks.getCategories(...args),
}))

const defer = () => {
  let resolve!: (value: any) => void
  let reject!: (error: Error) => void
  const promise = new Promise<any>((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}

describe('useGetCategories', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps the newest categories response when requests resolve out of order', async () => {
    const oldRequest = defer()
    const newRequest = defer()
    mocks.getCategories.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)
    const { categories, loading, loadCategories } = useGetCategories()

    const oldLoad = loadCategories()
    const newLoad = loadCategories()
    newRequest.resolve({ data: [{ category: 'new' }] })
    await newLoad

    oldRequest.resolve({ data: [{ category: 'old' }] })
    const oldResult = await oldLoad
    expect(categories.value).toEqual([{ category: 'new' }])
    expect(oldResult).toBe(false)
    expect(loading.value).toBe(false)
  })

  it('ignores a stale categories failure after a newer request succeeds', async () => {
    const oldRequest = defer()
    const newRequest = defer()
    mocks.getCategories.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)
    const { categories, loading, loadCategories } = useGetCategories()

    const oldLoad = loadCategories()
    const newLoad = loadCategories()
    newRequest.resolve({ data: [{ category: 'new' }] })
    await newLoad

    oldRequest.reject(new Error('stale failure'))
    await expect(oldLoad).resolves.toBe(false)
    expect(categories.value).toEqual([{ category: 'new' }])
    expect(loading.value).toBe(false)
  })
})

describe('useGetBuiltinTools', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps the newest tools response when requests resolve out of order', async () => {
    const oldRequest = defer()
    const newRequest = defer()
    mocks.getBuiltinTools.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)
    const { builtin_tools, loading, loadBuiltinTools } = useGetBuiltinTools()

    const oldLoad = loadBuiltinTools()
    const newLoad = loadBuiltinTools()
    newRequest.resolve({ data: [{ name: 'new-tool' }] })
    await newLoad

    oldRequest.resolve({ data: [{ name: 'old-tool' }] })
    const oldResult = await oldLoad
    expect(builtin_tools.value).toEqual([{ name: 'new-tool' }])
    expect(oldResult).toBe(false)
    expect(loading.value).toBe(false)
  })

  it('propagates the latest tools failure and clears loading', async () => {
    const error = new Error('tools failed')
    mocks.getBuiltinTools.mockRejectedValueOnce(error)
    const { loading, loadBuiltinTools } = useGetBuiltinTools()

    await expect(loadBuiltinTools()).rejects.toBe(error)
    expect(loading.value).toBe(false)
  })
})

describe('useGetBuiltinTool', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps the latest tool details when requests resolve out of order', async () => {
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

  it('ignores a stale tool detail rejection after a newer request succeeds', async () => {
    const oldRequest = defer()
    const newRequest = defer()
    mocks.getBuiltinTool.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)
    const { builtin_tool, loading, loadBuiltinTool } = useGetBuiltinTool()

    const oldLoad = loadBuiltinTool('provider', 'old')
    const newLoad = loadBuiltinTool('provider', 'new')
    newRequest.resolve({ data: { inputs: [{ name: 'new' }], params: [] } })
    await newLoad

    oldRequest.reject(new Error('stale tool request failed'))

    await expect(oldLoad).resolves.toBe(false)
    expect(builtin_tool.value.inputs).toEqual([{ name: 'new' }])
    expect(loading.value).toBe(false)
  })

  it('propagates the latest tool detail failure and clears loading', async () => {
    const error = new Error('current tool request failed')
    mocks.getBuiltinTool.mockRejectedValueOnce(error)
    const { loading, loadBuiltinTool } = useGetBuiltinTool()

    await expect(loadBuiltinTool('provider', 'current')).rejects.toBe(error)
    expect(loading.value).toBe(false)
  })
})
