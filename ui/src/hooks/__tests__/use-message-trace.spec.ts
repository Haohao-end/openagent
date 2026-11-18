import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGetMessageTrace } from '@/hooks/use-conversation'
import * as conversationService from '@/services/conversation'

vi.mock('@/services/conversation', () => ({
  deleteConversation: vi.fn(),
  deleteMessage: vi.fn(),
  getRecentConversations: vi.fn(),
  getConversationMessages: vi.fn(),
  getConversationName: vi.fn(),
  getMessageTrace: vi.fn(),
  updateConversationIsPinned: vi.fn(),
  updateConversationName: vi.fn(),
}))

describe('useGetMessageTrace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads message trace and sets state when request succeeds', async () => {
    const mockTrace = {
      message_id: 'msg-1',
      conversation_id: 'conv-1',
      app_id: 'app-1',
      status: 'normal',
      error: '',
      latency: 0.8,
      total_token_count: 88,
      total_price: 0.01,
      created_at: 1700000000,
      timeline: [],
    }
    vi.mocked(conversationService.getMessageTrace).mockResolvedValue({
      code: 'success',
      data: mockTrace,
    } as never)

    const { loading, trace, loadMessageTrace } = useGetMessageTrace()
    expect(loading.value).toBe(false)
    expect(trace.value).toBeNull()

    const promise = loadMessageTrace('msg-1')
    expect(loading.value).toBe(true)
    const result = await promise

    expect(result).toEqual(mockTrace)
    expect(trace.value).toEqual(mockTrace)
    expect(loading.value).toBe(false)
  })

  it('ignores stale response when a newer request is in-flight', async () => {
    let resolveFirst!: (value: any) => void
    let resolveSecond!: (value: any) => void

    const p1 = new Promise((resolve) => { resolveFirst = resolve })
    const p2 = new Promise((resolve) => { resolveSecond = resolve })

    vi.mocked(conversationService.getMessageTrace)
      .mockImplementationOnce(() => p1 as any)
      .mockImplementationOnce(() => p2 as any)

    const { loading, trace, loadMessageTrace } = useGetMessageTrace()

    const call1 = loadMessageTrace('msg-1')
    const call2 = loadMessageTrace('msg-2')

    resolveSecond({
      code: 'success',
      data: { message_id: 'msg-2', timeline: [] },
    })
    await call2

    expect(trace.value?.message_id).toBe('msg-2')

    resolveFirst({
      code: 'success',
      data: { message_id: 'msg-1', timeline: [] },
    })
    await call1

    // Should not be overwritten by msg-1
    expect(trace.value?.message_id).toBe('msg-2')
    expect(loading.value).toBe(false)
  })

  it('clears trace state and invalidates pending requests', async () => {
    let resolvePending!: (value: any) => void
    const pendingPromise = new Promise((resolve) => { resolvePending = resolve })
    vi.mocked(conversationService.getMessageTrace).mockImplementation(() => pendingPromise as any)

    const { loading, trace, loadMessageTrace, clearMessageTrace } = useGetMessageTrace()

    loadMessageTrace('msg-pending')
    expect(loading.value).toBe(true)

    clearMessageTrace()
    expect(loading.value).toBe(false)
    expect(trace.value).toBeNull()

    resolvePending({
      code: 'success',
      data: { message_id: 'msg-pending', timeline: [] },
    })
    await new Promise((r) => setTimeout(r, 0))

    expect(trace.value).toBeNull()
  })
})
