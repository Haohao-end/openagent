import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { post } from '@/utils/request'

const { routerPush } = vi.hoisted(() => ({
  routerPush: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/router', () => ({
  default: {
    currentRoute: {
      value: {
        name: 'pages-home',
        fullPath: '/home',
      },
    },
    push: routerPush,
  },
}))

describe('request utils', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses stored credentials safely when no active pinia exists', async () => {
    localStorage.setItem(
      'credential',
      JSON.stringify({
        access_token: 'stored-token',
        expire_at: Math.floor(Date.now() / 1000) + 3600,
      }),
    )

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: 'success',
          message: 'ok',
          data: { ok: true },
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const response = await post<{ data: { ok: boolean } }>('/notifications/test-1/read')

    expect(response.data.ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, requestInit] = fetchMock.mock.calls[0]
    const headers = requestInit?.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer stored-token')
  })
})
