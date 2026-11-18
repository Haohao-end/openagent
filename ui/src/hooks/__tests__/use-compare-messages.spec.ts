import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useCompareMessages } from '@/hooks/use-conversation'
import * as conversationService from '@/services/conversation'

vi.mock('@/services/conversation', () => ({
  compareMessages: vi.fn(),
  deleteConversation: vi.fn(),
  deleteMessage: vi.fn(),
  getRecentConversations: vi.fn(),
  getConversationMessages: vi.fn(),
  getConversationName: vi.fn(),
  getMessageTrace: vi.fn(),
  updateConversationIsPinned: vi.fn(),
  updateConversationName: vi.fn(),
}))

describe('useCompareMessages', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads run comparison and sets data when response succeeds', async () => {
    const mockData = {
      target: {
        id: 'msg-t',
        status: 'normal',
        error: '',
        latency: 1.5,
        total_token_count: 100,
        total_price: 0.01,
        answer_length: 50,
      },
      base: {
        id: 'msg-b',
        status: 'normal',
        error: '',
        latency: 1.2,
        total_token_count: 80,
        total_price: 0.008,
        answer_length: 45,
      },
      diff: {
        latency_diff: 0.3,
        total_token_count_diff: 20,
        message_token_count_diff: 10,
        answer_token_count_diff: 10,
        total_price_diff: 0.002,
        status_changed: false,
        error_changed: false,
        answer_match: false,
        answer_length_diff: 5,
      },
    }
    vi.mocked(conversationService.compareMessages).mockResolvedValue({
      code: 'success',
      data: mockData,
    } as never)

    const { loading, comparison, loadComparison } = useCompareMessages()
    expect(loading.value).toBe(false)
    expect(comparison.value).toBeNull()

    const promise = loadComparison('msg-t', 'msg-b')
    expect(loading.value).toBe(true)
    const result = await promise

    expect(result).toEqual(mockData)
    expect(comparison.value).toEqual(mockData)
    expect(loading.value).toBe(false)
  })

  it('ignores stale response when a newer comparison is in-flight', async () => {
    let resolveFirst!: (value: any) => void
    let resolveSecond!: (value: any) => void

    const p1 = new Promise((resolve) => { resolveFirst = resolve })
    const p2 = new Promise((resolve) => { resolveSecond = resolve })

    vi.mocked(conversationService.compareMessages)
      .mockImplementationOnce(() => p1 as any)
      .mockImplementationOnce(() => p2 as any)

    const { loading, comparison, loadComparison } = useCompareMessages()

    const call1 = loadComparison('msg-1', 'msg-base')
    const call2 = loadComparison('msg-2', 'msg-base')

    resolveSecond({
      code: 'success',
      data: { target: { id: 'msg-2' }, base: { id: 'msg-base' } },
    })
    await call2

    expect(comparison.value?.target.id).toBe('msg-2')

    resolveFirst({
      code: 'success',
      data: { target: { id: 'msg-1' }, base: { id: 'msg-base' } },
    })
    await call1

    expect(comparison.value?.target.id).toBe('msg-2')
    expect(loading.value).toBe(false)
  })

  it('clears comparison state and resets loading immediately', async () => {
    let resolvePending!: (value: any) => void
    const pendingPromise = new Promise((resolve) => { resolvePending = resolve })
    vi.mocked(conversationService.compareMessages).mockImplementation(() => pendingPromise as any)

    const { loading, comparison, loadComparison, clearComparison } = useCompareMessages()

    loadComparison('msg-t', 'msg-b')
    expect(loading.value).toBe(true)

    clearComparison()
    expect(loading.value).toBe(false)
    expect(comparison.value).toBeNull()

    resolvePending({
      code: 'success',
      data: { target: { id: 'msg-t' } },
    })
    await new Promise((r) => setTimeout(r, 0))

    expect(comparison.value).toBeNull()
  })
})
