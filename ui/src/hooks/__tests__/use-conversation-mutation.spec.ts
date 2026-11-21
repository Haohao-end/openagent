import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useDeleteConversation, useDeleteMessage, useUpdateConversationName } from '@/hooks/use-conversation'
import * as conversationService from '@/services/conversation'
import { Message, Modal } from '@arco-design/web-vue'

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

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
  },
  Modal: {
    warning: vi.fn(),
  },
}))

describe('useDeleteConversation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('surfaces the request error and skips the callback when deletion fails', async () => {
    const callback = vi.fn()
    const { handleDeleteConversation } = useDeleteConversation()
    handleDeleteConversation('c1', callback)
    const onOk = vi.mocked(Modal.warning).mock.calls[0][0].onOk as () => Promise<void>

    const error = new Error('delete failed')
    vi.mocked(conversationService.deleteConversation).mockRejectedValueOnce(error)
    await expect(onOk()).rejects.toBe(error)
    expect(callback).not.toHaveBeenCalled()
    expect(Message.success).not.toHaveBeenCalled()
    expect(Message.error).toHaveBeenCalledWith('delete failed')

    vi.mocked(conversationService.deleteConversation).mockResolvedValueOnce({ message: 'deleted' } as any)
    await onOk()
    expect(callback).toHaveBeenCalledOnce()
    expect(Message.success).toHaveBeenCalledWith('deleted')
  })
})

describe('useDeleteMessage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps loading true while any concurrent delete request is in flight', async () => {
    let resolveFirst!: () => void
    let resolveSecond!: () => void

    const p1 = new Promise<void>((resolve) => { resolveFirst = resolve })
    const p2 = new Promise<void>((resolve) => { resolveSecond = resolve })

    vi.mocked(conversationService.deleteMessage)
      .mockImplementationOnce(() => p1 as any)
      .mockImplementationOnce(() => p2 as any)

    const { loading, handleDeleteMessage } = useDeleteMessage()

    const d1 = handleDeleteMessage('c1', 'm1')
    const d2 = handleDeleteMessage('c1', 'm2')
    expect(loading.value).toBe(true)

    // First finishes, but second is still pending
    resolveFirst()
    await d1
    expect(loading.value).toBe(true)

    // Second finishes, loading becomes false
    resolveSecond()
    await d2
    expect(loading.value).toBe(false)
  })
})

describe('useUpdateConversationName', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('guards success message and loading against stale rename completion', async () => {
    let resolveFirst!: (value: any) => void
    let resolveSecond!: (value: any) => void

    const p1 = new Promise((resolve) => { resolveFirst = resolve })
    const p2 = new Promise((resolve) => { resolveSecond = resolve })

    vi.mocked(conversationService.updateConversationName)
      .mockImplementationOnce(() => p1 as any)
      .mockImplementationOnce(() => p2 as any)

    const { loading, handleUpdateConversationName } = useUpdateConversationName()

    const r1 = handleUpdateConversationName('c1', 'Name 1')
    const r2 = handleUpdateConversationName('c1', 'Name 2')

    resolveSecond({ message: 'Updated to Name 2' })
    await r2
    expect(Message.success).toHaveBeenCalledWith('Updated to Name 2')
    expect(loading.value).toBe(false)

    resolveFirst({ message: 'Updated to Name 1' })
    await r1
    // Stale r1 should not trigger success toast
    expect(Message.success).not.toHaveBeenCalledWith('Updated to Name 1')
    expect(loading.value).toBe(false)
  })
})
