import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Modal } from '@arco-design/web-vue'
import { createRequestError } from '@/utils/error'
import {
  useCreateApiToolProvider,
  useDeleteApiToolProvider,
  useGetApiToolProvider,
  useUpdateApiToolProvider,
  useGetApiTool,
  useGetApiToolProvidersWithPage,
  useValidateOpenAPISchema,
  useGenerateIconPreview,
} from '@/hooks/use-tool'

const mocks = vi.hoisted(() => ({
  createApiToolProvider: vi.fn(),
  deleteApiToolProvider: vi.fn(),
  generateIconPreview: vi.fn(),
  getApiTool: vi.fn(),
  getApiToolProvider: vi.fn(),
  getApiToolProvidersWithPage: vi.fn(),
  regenerateIcon: vi.fn(),
  updateApiToolProvider: vi.fn(),
  validateOpenAPISchema: vi.fn(),
}))

const messageSuccessMock = vi.fn()
const messageErrorMock = vi.fn()

vi.mock('@/services/api-tool', () => ({
  createApiToolProvider: (...args: unknown[]) => mocks.createApiToolProvider(...args),
  deleteApiToolProvider: (...args: unknown[]) => mocks.deleteApiToolProvider(...args),
  generateIconPreview: (...args: unknown[]) => mocks.generateIconPreview(...args),
  getApiTool: (...args: unknown[]) => mocks.getApiTool(...args),
  getApiToolProvider: (...args: unknown[]) => mocks.getApiToolProvider(...args),
  getApiToolProvidersWithPage: (...args: unknown[]) => mocks.getApiToolProvidersWithPage(...args),
  regenerateIcon: (...args: unknown[]) => mocks.regenerateIcon(...args),
  updateApiToolProvider: (...args: unknown[]) => mocks.updateApiToolProvider(...args),
  validateOpenAPISchema: (...args: unknown[]) => mocks.validateOpenAPISchema(...args),
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

describe('use-tool request feedback', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('suppresses icon errors when the caller invalidates its request', async () => {
    mocks.generateIconPreview.mockRejectedValueOnce(new Error('generation failed'))
    const { handleGenerateIconPreview } = useGenerateIconPreview()

    await expect(handleGenerateIconPreview('tool', '', () => false)).rejects.toThrow(
      'generation failed',
    )

    expect(messageErrorMock).not.toHaveBeenCalled()
  })

  it('returns true when OpenAPI validation succeeds', async () => {
    mocks.validateOpenAPISchema.mockResolvedValue({
      message: '数据校验成功',
    })

    const { handleValidateOpenAPISchema } = useValidateOpenAPISchema()
    const result = await handleValidateOpenAPISchema('{"server":"https://example.com"}')

    expect(result).toBe(true)
    expect(mocks.validateOpenAPISchema).toHaveBeenCalledWith('{"server":"https://example.com"}')
    expect(messageSuccessMock).toHaveBeenCalledWith('数据校验成功')
    expect(messageErrorMock).not.toHaveBeenCalled()
  })

  it('returns false and shows backend error when OpenAPI validation fails', async () => {
    mocks.validateOpenAPISchema.mockRejectedValue(
      createRequestError({
        message: 'URL解析到不允许的地址: 127.0.0.1',
      }),
    )

    const { handleValidateOpenAPISchema } = useValidateOpenAPISchema()
    const result = await handleValidateOpenAPISchema('{"server":"http://127.0.0.1"}')

    expect(result).toBe(false)
    expect(messageErrorMock).toHaveBeenCalledWith('URL解析到不允许的地址: 127.0.0.1')
    expect(messageSuccessMock).not.toHaveBeenCalled()
  })

  it('returns false and keeps the create flow open when tool creation fails', async () => {
    mocks.createApiToolProvider.mockRejectedValue(
      createRequestError({
        message: 'URL解析到不允许的地址: 10.0.0.1',
      }),
    )

    const { handleCreateApiToolProvider } = useCreateApiToolProvider()
    const result = await handleCreateApiToolProvider({
      name: 'demo',
      description: 'demo api',
      icon: 'https://example.com/icon.png',
      openapi_schema: '{"server":"http://10.0.0.1"}',
      headers: [],
    } as any)

    expect(result).toBe(false)
    expect(messageErrorMock).toHaveBeenCalledWith('URL解析到不允许的地址: 10.0.0.1')
    expect(messageSuccessMock).not.toHaveBeenCalled()
  })

  it('returns false and keeps the update flow open when tool update fails', async () => {
    mocks.updateApiToolProvider.mockRejectedValue(
      createRequestError({
        message: 'URL解析到不允许的地址: 127.0.0.1',
      }),
    )

    const { handleUpdateApiToolProvider } = useUpdateApiToolProvider()
    const result = await handleUpdateApiToolProvider(
      'provider-1',
      {
        name: 'demo',
        description: 'demo api',
        icon: 'https://example.com/icon.png',
        openapi_schema: '{"server":"http://127.0.0.1"}',
        headers: [],
      } as any,
    )

    expect(result).toBe(false)
    expect(messageErrorMock).toHaveBeenCalledWith('URL解析到不允许的地址: 127.0.0.1')
    expect(messageSuccessMock).not.toHaveBeenCalled()
  })

  it('calls the API tool provider delete callback only after success', async () => {
    mocks.deleteApiToolProvider.mockResolvedValueOnce({ message: 'deleted' })
    const warningSpy = vi.spyOn(Modal, 'warning').mockImplementation(() => undefined as never)
    const callback = vi.fn()
    const { handleDelete } = useDeleteApiToolProvider()

    handleDelete('provider-1', callback)
    const onOk = warningSpy.mock.calls[0][0].onOk as () => Promise<void>
    await onOk()

    expect(callback).toHaveBeenCalledOnce()
    expect(messageSuccessMock).toHaveBeenCalledWith('deleted')
  })

  it('does not call the API tool provider delete callback when deletion fails', async () => {
    const requestError = new Error('delete failed')
    mocks.deleteApiToolProvider.mockRejectedValueOnce(requestError)
    const warningSpy = vi.spyOn(Modal, 'warning').mockImplementation(() => undefined as never)
    const callback = vi.fn()
    const { handleDelete } = useDeleteApiToolProvider()

    handleDelete('provider-1', callback)
    const onOk = warningSpy.mock.calls[0][0].onOk as () => Promise<void>
    await expect(onOk()).rejects.toBe(requestError)

    expect(callback).not.toHaveBeenCalled()
    expect(messageSuccessMock).not.toHaveBeenCalled()
  })

  it('keeps the latest tool provider search when requests resolve out of order', async () => {
    const defer = () => {
      let resolve!: (value: any) => void
      const promise = new Promise<any>((done) => { resolve = done })
      return { promise, resolve }
    }
    const oldRequest = defer()
    const newRequest = defer()
    mocks.getApiToolProvidersWithPage.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)
    const { api_tool_providers, loadApiToolProviders } = useGetApiToolProvidersWithPage()

    const oldLoad = loadApiToolProviders(true, 'old')
    const newLoad = loadApiToolProviders(true, 'new')
    newRequest.resolve({ data: { list: [{ id: 'new' }], paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 } } })
    await newLoad
    oldRequest.resolve({ data: { list: [{ id: 'old' }], paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 } } })
    await oldLoad

    expect(api_tool_providers.value).toEqual([{ id: 'new' }])
  })

  it('ignores a stale tool provider search failure after a newer search succeeds', async () => {
    const defer = () => {
      let resolve!: (value: any) => void
      let reject!: (error: Error) => void
      const promise = new Promise<any>((done, fail) => {
        resolve = done
        reject = fail
      })
      return { promise, resolve, reject }
    }
    const olderResponse = defer()
    const newerResponse = defer()
    mocks.getApiToolProvidersWithPage.mockReturnValueOnce(olderResponse.promise).mockReturnValueOnce(newerResponse.promise)
    const { api_tool_providers, loading, loadApiToolProviders } = useGetApiToolProvidersWithPage()

    const olderRequest = loadApiToolProviders(true, 'old')
    const newerRequest = loadApiToolProviders(true, 'new')
    newerResponse.resolve({
      data: {
        list: [{ id: 'new' }],
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
      },
    })
    await newerRequest

    olderResponse.reject(new Error('stale tool provider search failed'))

    await expect(olderRequest).resolves.toBeUndefined()
    expect(api_tool_providers.value).toEqual([{ id: 'new' }])
    expect(loading.value).toBe(false)
  })

  it('propagates the latest tool provider search failure and clears loading', async () => {
    const requestError = new Error('current tool provider search failed')
    mocks.getApiToolProvidersWithPage.mockRejectedValueOnce(requestError)
    const { loading, loadApiToolProviders } = useGetApiToolProvidersWithPage()

    await expect(loadApiToolProviders(true, 'current')).rejects.toBe(requestError)
    expect(loading.value).toBe(false)
  })

  it('does not invalidate in-flight initial load when concurrent scroll triggers pagination', async () => {
    const defer = () => {
      let resolve!: (value: any) => void
      const promise = new Promise<any>((done) => { resolve = done })
      return { promise, resolve }
    }
    const initialResponse = defer()
    mocks.getApiToolProvidersWithPage.mockReturnValueOnce(initialResponse.promise)

    const { loading, api_tool_providers, paginator, loadApiToolProviders } = useGetApiToolProvidersWithPage()

    const initialRequest = loadApiToolProviders(true)
    expect(loading.value).toBe(true)

    const scrollRequest = loadApiToolProviders(false)
    await scrollRequest

    expect(mocks.getApiToolProvidersWithPage).toHaveBeenCalledTimes(1)
    expect(loading.value).toBe(true)

    initialResponse.resolve({
      data: {
        list: [{ id: 'provider-1' }],
        paginator: { current_page: 1, page_size: 20, total_page: 2, total_record: 25 },
      },
    })
    await initialRequest

    expect(api_tool_providers.value).toEqual([{ id: 'provider-1' }])
    expect(paginator.value.current_page).toBe(2)
    expect(loading.value).toBe(false)
  })

  it('does not increment generation or alter loading when pagination is called without more pages', async () => {
    const { loading, paginator, loadApiToolProviders } = useGetApiToolProvidersWithPage()
    paginator.value = { current_page: 3, page_size: 20, total_page: 2, total_record: 25 }

    await loadApiToolProviders(false)

    expect(mocks.getApiToolProvidersWithPage).not.toHaveBeenCalled()
    expect(loading.value).toBe(false)
  })

  it('keeps the latest API tool details when requests resolve out of order', async () => {
    const defer = () => {
      let resolve!: (value: any) => void
      const promise = new Promise<any>((done) => { resolve = done })
      return { promise, resolve }
    }
    const olderResponse = defer()
    const newerResponse = defer()
    mocks.getApiTool.mockReturnValueOnce(olderResponse.promise).mockReturnValueOnce(newerResponse.promise)
    const { api_tool, loadApiTool } = useGetApiTool()

    const olderRequest = loadApiTool('provider', 'old')
    const newerRequest = loadApiTool('provider', 'new')
    newerResponse.resolve({ data: { name: 'new' } })
    await newerRequest
    olderResponse.resolve({ data: { name: 'old' } })
    const olderResult = await olderRequest

    expect(api_tool.value).toEqual({ name: 'new' })
    expect(olderResult).toBe(false)
  })

  it('ignores a stale API tool detail failure after a newer request succeeds', async () => {
    const defer = () => {
      let resolve!: (value: any) => void
      let reject!: (error: Error) => void
      const promise = new Promise<any>((done, fail) => {
        resolve = done
        reject = fail
      })
      return { promise, resolve, reject }
    }
    const olderResponse = defer()
    const newerResponse = defer()
    mocks.getApiTool.mockReturnValueOnce(olderResponse.promise).mockReturnValueOnce(newerResponse.promise)
    const { api_tool, loading, loadApiTool } = useGetApiTool()

    const olderRequest = loadApiTool('provider', 'old')
    const newerRequest = loadApiTool('provider', 'new')
    newerResponse.resolve({ data: { name: 'new' } })
    await newerRequest

    olderResponse.reject(new Error('stale API tool request failed'))

    await expect(olderRequest).resolves.toBe(false)
    expect(api_tool.value).toEqual({ name: 'new' })
    expect(loading.value).toBe(false)
  })

  it('propagates the latest API tool detail failure and clears loading', async () => {
    const requestError = new Error('current API tool request failed')
    mocks.getApiTool.mockRejectedValueOnce(requestError)
    const { loading, loadApiTool } = useGetApiTool()

    await expect(loadApiTool('provider', 'current')).rejects.toBe(requestError)
    expect(loading.value).toBe(false)
  })
})

describe('useGetApiToolProvider race conditions', () => {
  it('loads provider details and resets loading', async () => {
    mocks.getApiToolProvider.mockResolvedValueOnce({ data: { id: 'p1', name: 'Provider 1' } })
    const { loading, api_tool_provider, loadApiToolProvider } = useGetApiToolProvider()

    await loadApiToolProvider('p1')

    expect(api_tool_provider.value).toEqual({ id: 'p1', name: 'Provider 1' })
    expect(loading.value).toBe(false)
  })

  it('discards stale provider response and maintains loading while newer request is pending', async () => {
    let resolveOlder: (v: any) => void = () => {}
    let resolveNewer: (v: any) => void = () => {}

    mocks.getApiToolProvider
      .mockImplementationOnce(() => new Promise((res) => { resolveOlder = res }))
      .mockImplementationOnce(() => new Promise((res) => { resolveNewer = res }))

    const { loading, api_tool_provider, loadApiToolProvider } = useGetApiToolProvider()

    const call1 = loadApiToolProvider('p-old')
    const call2 = loadApiToolProvider('p-new')

    expect(loading.value).toBe(true)

    resolveOlder({ data: { id: 'p-old', name: 'Old' } })
    await Promise.resolve()

    expect(api_tool_provider.value).toEqual({})
    expect(loading.value).toBe(true)

    resolveNewer({ data: { id: 'p-new', name: 'New' } })
    await Promise.all([call1, call2])

    expect(api_tool_provider.value).toEqual({ id: 'p-new', name: 'New' })
    expect(loading.value).toBe(false)
  })

  it('resets loading when latest provider request fails', async () => {
    mocks.getApiToolProvider.mockRejectedValueOnce(new Error('fetch error'))
    const { loading, loadApiToolProvider } = useGetApiToolProvider()

    await expect(loadApiToolProvider('p1')).rejects.toThrow('fetch error')
    expect(loading.value).toBe(false)
  })
})
