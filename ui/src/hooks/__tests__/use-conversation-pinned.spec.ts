import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useUpdateConversationIsPinned } from '@/hooks/use-conversation'
import * as conversationService from '@/services/conversation'
import { Message } from '@arco-design/web-vue'

vi.mock('@/services/conversation', () => ({
  updateConversationIsPinned: vi.fn(),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('useUpdateConversationIsPinned', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('guards success message and loading against stale pinning completion', async () => {
    let resolveFirst!: (value: any) => void
    let resolveSecond!: (value: any) => void

    const p1 = new Promise((resolve) => { resolveFirst = resolve })
    const p2 = new Promise((resolve) => { resolveSecond = resolve })

    vi.mocked(conversationService.updateConversationIsPinned)
      .mockImplementationOnce(() => p1 as any)
      .mockImplementationOnce(() => p2 as any)

    const { loading, handleUpdateConversationIsPinned } = useUpdateConversationIsPinned()

    const r1 = handleUpdateConversationIsPinned('c1', true)
    const r2 = handleUpdateConversationIsPinned('c1', false)

    // Second completes first
    resolveSecond({ message: 'Pinned: false' })
    await r2
    expect(Message.success).toHaveBeenCalledWith('Pinned: false')
    expect(loading.value).toBe(false)

    // First completes second (stale)
    resolveFirst({ message: 'Pinned: true' })
    await r1
    
    // Stale r1 should not trigger success toast or reset loading if not already false (or it should not affect final state)
    // Currently it WILL trigger, which is the bug
    expect(Message.success).toHaveBeenCalledTimes(1)
  })
})
