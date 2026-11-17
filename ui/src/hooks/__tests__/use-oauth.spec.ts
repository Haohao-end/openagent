import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthorize, useProvider } from '@/hooks/use-oauth'
import * as oauthService from '@/services/oauth'

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@/services/oauth', () => ({
  provider: vi.fn(),
  authorize: vi.fn(),
}))

describe('useProvider race conditions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('updates redirect_url and manages loading state', async () => {
    vi.mocked(oauthService.provider).mockResolvedValue({
      data: { redirect_url: 'https://github.com/login/oauth/authorize?client_id=123' },
    } as never)

    const { loading, redirect_url, handleProvider } = useProvider()
    expect(loading.value).toBe(false)

    await handleProvider('github')

    expect(oauthService.provider).toHaveBeenCalledWith('github')
    expect(redirect_url.value).toBe('https://github.com/login/oauth/authorize?client_id=123')
    expect(loading.value).toBe(false)
  })

  it('discards stale provider response and maintains loading for latest request', async () => {
    let resolveFirst: (value: any) => void = () => {}
    let resolveSecond: (value: any) => void = () => {}

    vi.mocked(oauthService.provider)
      .mockImplementationOnce(() => new Promise((res) => { resolveFirst = res }))
      .mockImplementationOnce(() => new Promise((res) => { resolveSecond = res }))

    const { loading, redirect_url, handleProvider } = useProvider()

    const firstCall = handleProvider('github')
    const secondCall = handleProvider('google')

    expect(loading.value).toBe(true)

    resolveFirst({ data: { redirect_url: 'https://github.com/oauth' } })
    await Promise.resolve()

    expect(redirect_url.value).toBe('')
    expect(loading.value).toBe(true)

    resolveSecond({ data: { redirect_url: 'https://accounts.google.com/oauth' } })
    await Promise.all([firstCall, secondCall])

    expect(redirect_url.value).toBe('https://accounts.google.com/oauth')
    expect(loading.value).toBe(false)
  })

  it('resets loading state when the latest request fails', async () => {
    vi.mocked(oauthService.provider).mockRejectedValue(new Error('Network error'))

    const { loading, handleProvider } = useProvider()
    await expect(handleProvider('github')).rejects.toThrow('Network error')

    expect(loading.value).toBe(false)
  })
})

describe('useAuthorize race conditions', () => {
  it('updates authorization and resets loading', async () => {
    vi.mocked(oauthService.authorize).mockResolvedValue({
      data: { access_token: 'auth-token-123' },
    } as never)

    const { loading, authorization, handleAuthorize } = useAuthorize()
    await handleAuthorize('github', 'oauth-code-1')

    expect(oauthService.authorize).toHaveBeenCalledWith('github', 'oauth-code-1', 'login')
    expect(authorization.value).toEqual({ access_token: 'auth-token-123' })
    expect(loading.value).toBe(false)
  })

  it('discards stale authorization and maintains loading while newer request is pending', async () => {
    let resolveFirst: (v: any) => void = () => {}
    let resolveSecond: (v: any) => void = () => {}

    vi.mocked(oauthService.authorize)
      .mockImplementationOnce(() => new Promise((res) => { resolveFirst = res }))
      .mockImplementationOnce(() => new Promise((res) => { resolveSecond = res }))

    const { loading, authorization, handleAuthorize } = useAuthorize()

    const call1 = handleAuthorize('github', 'code-old')
    const call2 = handleAuthorize('github', 'code-new')

    expect(loading.value).toBe(true)

    resolveFirst({ data: { access_token: 'old-token' } })
    await Promise.resolve()

    expect(authorization.value).toEqual({})
    expect(loading.value).toBe(true)

    resolveSecond({ data: { access_token: 'new-token' } })
    await Promise.all([call1, call2])

    expect(authorization.value).toEqual({ access_token: 'new-token' })
    expect(loading.value).toBe(false)
  })

  it('resets loading when authorization fails', async () => {
    vi.mocked(oauthService.authorize).mockRejectedValue(new Error('oauth error'))

    const { loading, handleAuthorize } = useAuthorize()
    await expect(handleAuthorize('github', 'code')).rejects.toThrow('oauth error')

    expect(loading.value).toBe(false)
  })
})
