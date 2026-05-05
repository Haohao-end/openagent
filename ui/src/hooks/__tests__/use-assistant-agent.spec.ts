import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDeleteAssistantAgentConversation } from '@/hooks/use-assistant-agent'
import * as assistantAgentService from '@/services/assistant-agent'
import { Message } from '@arco-design/web-vue'

vi.mock('@/services/assistant-agent', () => ({
  assistantAgentChat: vi.fn(),
  assistantAgentGenerateIntroduction: vi.fn(),
  deleteAssistantAgentConversation: vi.fn(),
  getAssistantAgentConversations: vi.fn(),
  getAssistantAgentMessagesWithPage: vi.fn(),
  stopAssistantAgentChat: vi.fn(),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
  },
}))

describe('useDeleteAssistantAgentConversation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(assistantAgentService.deleteAssistantAgentConversation).mockResolvedValue({
      message: '清空会话成功',
    } as never)
  })

  it('shows success by default', async () => {
    const { loading, handleDeleteAssistantAgentConversation } =
      useDeleteAssistantAgentConversation()

    await handleDeleteAssistantAgentConversation()

    expect(assistantAgentService.deleteAssistantAgentConversation).toHaveBeenCalledTimes(1)
    expect(Message.success).toHaveBeenCalledWith('清空会话成功')
    expect(loading.value).toBe(false)
  })

  it('can suppress success toast for sidebar new conversation navigation', async () => {
    const { loading, handleDeleteAssistantAgentConversation } =
      useDeleteAssistantAgentConversation()

    await handleDeleteAssistantAgentConversation({ showSuccess: false })

    expect(assistantAgentService.deleteAssistantAgentConversation).toHaveBeenCalledTimes(1)
    expect(Message.success).not.toHaveBeenCalled()
    expect(loading.value).toBe(false)
  })
})
