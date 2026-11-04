import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { post, ssePost, upload } from '@/utils/request'

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

  it('dispatches the last SSE event when EOF follows an unterminated data line', async () => {
    const onData = vi.fn()
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('event: message\ndata: {"content":"final"}'))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    })))

    await ssePost('/stream', {}, onData)

    expect(onData).toHaveBeenCalledWith({ event: 'message', data: { content: 'final' } })
  })

  it('dispatches events separated by CR-only lines across chunks', async () => {
    const onData = vi.fn()
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('event: message\rdata: {"content":"cr-only"}\r'))
        controller.enqueue(new TextEncoder().encode('\r'))
        controller.enqueue(new TextEncoder().encode('event: message\r\ndata: {"content":\r'))
        controller.enqueue(new TextEncoder().encode('\ndata: "crlf"}\r\r'))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    })))

    await ssePost('/stream', {}, onData)

    expect(onData).toHaveBeenCalledWith({ event: 'message', data: { content: 'cr-only' } })
    expect(onData).toHaveBeenNthCalledWith(2, { event: 'message', data: { content: 'crlf' } })
  })

  it('joins multiple SSE data fields before parsing JSON', async () => {
    const onData = vi.fn()
    const stream = 'event: message\ndata: {"content":\ndata: "joined"}\n\n'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    })))
    await ssePost('/stream', {}, onData)
    expect(onData).toHaveBeenCalledWith({ event: 'message', data: { content: 'joined' } })
  })

  it('dispatches data frames without an event field as message events', async () => {
    const onData = vi.fn()
    const stream = 'data: {"content":"default-event"}\n\n'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, {
      headers: { 'Content-Type': 'text/event-stream' },
    })))

    await ssePost('/stream', {}, onData)

    expect(onData).toHaveBeenCalledWith({ event: 'message', data: { content: 'default-event' } })
  })

  it('rejects uploads that stall instead of leaving the promise pending', async () => {
    let xhrInstance!: XMLHttpRequest
    class FakeXMLHttpRequest {
      readyState = 0
      status = 0
      response = null
      timeout = 0
      ontimeout: ((event: ProgressEvent) => void) | null = null
      responseType: XMLHttpRequestResponseType = 'json'
      withCredentials = false
      upload = { onprogress: null as ((event: ProgressEvent) => void) | null }
      onreadystatechange: (() => void) | null = null
      onerror: (() => void) | null = null
      open = vi.fn()
      setRequestHeader = vi.fn()
      send = vi.fn()
      constructor() {
        xhrInstance = this as unknown as XMLHttpRequest
      }
    }
    vi.stubGlobal('XMLHttpRequest', FakeXMLHttpRequest)

    const request = upload('/files/upload')
    expect(xhrInstance.timeout).toBe(100000)
    expect(xhrInstance.ontimeout).toBeTypeOf('function')
    xhrInstance.ontimeout?.(new ProgressEvent('timeout'))
    await expect(request).rejects.toMatchObject({ message: '上传超时' })
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
