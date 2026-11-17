import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGetAppConversations, useGetWebApp, useWebAppChat } from '@/hooks/use-web-app'
import { getWebApp, getWebAppConversations, webAppChat } from '@/services/web-app'
import { Message } from '@arco-design/web-vue'

vi.mock('@/services/web-app', () => ({
  webAppChat: vi.fn(),
  getWebApp: vi.fn(),
  getWebAppConversations: vi.fn(),
}))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: vi.fn() } }))

const defer = () => {
  let resolve!: (value: any) => void
  let reject!: (error: Error) => void
  const promise = new Promise<any>((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useGetWebApp', () => {
  it('keeps the latest web app details when requests resolve out of order', async () => {
    const olderResponse = defer()
    const newerResponse = defer()
    vi.mocked(getWebApp).mockReturnValueOnce(olderResponse.promise).mockReturnValueOnce(newerResponse.promise)
    const { web_app, loading, loadWebApp } = useGetWebApp()

    const olderRequest = loadWebApp('token-old')
    const newerRequest = loadWebApp('token-new')
    newerResponse.resolve({ data: { name: 'app-new' } })
    await newerRequest
    olderResponse.resolve({ data: { name: 'app-old' } })
    const oldResult = await olderRequest

    expect(web_app.value).toEqual({ name: 'app-new' })
    expect(oldResult).toBe(false)
    expect(loading.value).toBe(false)
  })

  it('ignores a stale web app error after a newer request succeeds', async () => {
    const olderResponse = defer()
    const newerResponse = defer()
    vi.mocked(getWebApp).mockReturnValueOnce(olderResponse.promise).mockReturnValueOnce(newerResponse.promise)
    const { web_app, loading, loadWebApp } = useGetWebApp()

    const olderRequest = loadWebApp('token-old')
    const newerRequest = loadWebApp('token-new')
    newerResponse.resolve({ data: { name: 'app-new' } })
    await newerRequest

    olderResponse.reject(new Error('stale app error'))
    await expect(olderRequest).resolves.toBe(false)
    expect(web_app.value).toEqual({ name: 'app-new' })
    expect(loading.value).toBe(false)
  })
})

describe('useGetAppConversations', () => {
  it('keeps the latest conversations when requests resolve out of order', async () => {
    const olderResponse = defer()
    const newerResponse = defer()
    vi.mocked(getWebAppConversations)
      .mockReturnValueOnce(olderResponse.promise)
      .mockReturnValueOnce(olderResponse.promise)
      .mockReturnValueOnce(newerResponse.promise)
      .mockReturnValueOnce(newerResponse.promise)
    const { pinned_conversations, loading, loadWebAppConversations } = useGetAppConversations()

    const olderRequest = loadWebAppConversations('token-old')
    const newerRequest = loadWebAppConversations('token-new')
    newerResponse.resolve({ data: [{ id: 'new-pinned' }] })
    await newerRequest

    olderResponse.resolve({ data: [{ id: 'old-pinned' }] })
    const oldResult = await olderRequest

    expect(pinned_conversations.value).toEqual([{ id: 'new-pinned' }])
    expect(oldResult).toBe(false)
    expect(loading.value).toBe(false)
  })
})

describe('useWebAppChat', () => {
  it('silently finishes a chat canceled by its caller', async () => {
    vi.mocked(webAppChat).mockRejectedValueOnce(new Error('request canceled'))
    const controller = new AbortController()
    const { handleWebAppChat } = useWebAppChat()
    const request = handleWebAppChat('token-1', {
      query: 'hello',
      conversation_id: '',
      image_urls: [],
      enable_deep_thinking: false,
    }, vi.fn(), controller.signal)

    controller.abort()
    await expect(request).resolves.toBeUndefined()
    expect(Message.error).not.toHaveBeenCalled()
  })
})
