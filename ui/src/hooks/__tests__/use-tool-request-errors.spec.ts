import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRequestError } from '@/utils/error'
import {
  useCreateApiToolProvider,
  useUpdateApiToolProvider,
  useGetApiTool,
  useGetApiToolProvidersWithPage,
  useValidateOpenAPISchema,
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
})
