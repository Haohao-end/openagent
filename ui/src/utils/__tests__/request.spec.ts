import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { post, upload } from '@/utils/request'

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

  it('does not log upload response bodies', async () => {
    const response = { code: 'success', message: 'ok', data: { id: 'private-file-id' } }
    class FakeXMLHttpRequest {
      readyState = 0
      status = 200
      response = response
      responseType: XMLHttpRequestResponseType = 'json'
      withCredentials = false
      upload = { onprogress: null as ((event: ProgressEvent) => void) | null }
      onreadystatechange: (() => void) | null = null
      onerror: (() => void) | null = null
      open = vi.fn()
      setRequestHeader = vi.fn()
      send = vi.fn(() => {
        this.readyState = 4
        this.onreadystatechange?.()
      })
    }
    const log = vi.spyOn(console, 'log').mockImplementation(() => {})
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.stubGlobal('XMLHttpRequest', FakeXMLHttpRequest)

    try {
      await expect(upload('/files/upload')).resolves.toEqual(response)
      expect(log).not.toHaveBeenCalled()
      expect(error).not.toHaveBeenCalled()
    } finally {
      log.mockRestore()
      error.mockRestore()
    }
  })
})
