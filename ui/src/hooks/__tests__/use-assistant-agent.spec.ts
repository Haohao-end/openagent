import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  useAssistantAgentChat,
  useDeleteAssistantAgentConversation,
  useGetAssistantAgentCapabilities,
  useGetAssistantAgentConversations,
} from '@/hooks/use-assistant-agent'
import * as assistantAgentService from '@/services/assistant-agent'
import { Message } from '@arco-design/web-vue'

vi.mock('@/services/assistant-agent', () => ({
  assistantAgentChat: vi.fn(),
  assistantAgentGenerateIntroduction: vi.fn(),
  deleteAssistantAgentConversation: vi.fn(),
  getAssistantAgentCapabilities: vi.fn(),
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

describe('useAssistantAgentChat', () => {
  it('forwards the cancellation signal to the chat service', async () => {
    const controller = new AbortController()
    vi.mocked(assistantAgentService.assistantAgentChat).mockResolvedValue(undefined as never)
    const { handleAssistantAgentChat } = useAssistantAgentChat()

    await handleAssistantAgentChat('question', [], '', vi.fn(), false, controller.signal)

    expect(assistantAgentService.assistantAgentChat).toHaveBeenCalledWith(
      'question',
      [],
      '',
      expect.any(Function),
      false,
      controller.signal,
    )
  })
})

describe('useGetAssistantAgentConversations race conditions', () => {
  it('loads conversations and resets loading state', async () => {
    const list = [{ id: 'conv-1', name: 'Chat 1' }]
    vi.mocked(assistantAgentService.getAssistantAgentConversations).mockResolvedValue({
      data: list,
    } as never)

    const { loading, conversations, loadAssistantAgentConversations } =
      useGetAssistantAgentConversations()

    await loadAssistantAgentConversations()

    expect(conversations.value).toEqual(list)
    expect(loading.value).toBe(false)
  })

  it('discards stale conversations and preserves loading until latest resolves', async () => {
    let resolveFirst: (v: any) => void = () => {}
    let resolveSecond: (v: any) => void = () => {}

    vi.mocked(assistantAgentService.getAssistantAgentConversations)
      .mockImplementationOnce(() => new Promise((res) => { resolveFirst = res }))
      .mockImplementationOnce(() => new Promise((res) => { resolveSecond = res }))

    const { loading, conversations, loadAssistantAgentConversations } =
      useGetAssistantAgentConversations()

    const call1 = loadAssistantAgentConversations()
    const call2 = loadAssistantAgentConversations()

    expect(loading.value).toBe(true)

    resolveFirst({ data: [{ id: 'stale', name: 'Stale' }] })
    await Promise.resolve()

    expect(conversations.value).toEqual([])
    expect(loading.value).toBe(true)

    resolveSecond({ data: [{ id: 'latest', name: 'Latest' }] })
    await Promise.all([call1, call2])

    expect(conversations.value).toEqual([{ id: 'latest', name: 'Latest' }])
    expect(loading.value).toBe(false)
  })
})

describe('useGetAssistantAgentCapabilities race conditions', () => {
  it('loads capabilities and resets loading state', async () => {
    vi.mocked(assistantAgentService.getAssistantAgentCapabilities).mockResolvedValue({
      data: { capabilities: { web_search: true } },
    } as never)

    const { loading, capabilities, loadAssistantAgentCapabilities } =
      useGetAssistantAgentCapabilities()

    await loadAssistantAgentCapabilities()

    expect(capabilities.value).toEqual({ web_search: true })
    expect(loading.value).toBe(false)
  })

  it('discards stale capabilities and preserves loading until latest resolves', async () => {
    let resolveFirst: (v: any) => void = () => {}
    let resolveSecond: (v: any) => void = () => {}

    vi.mocked(assistantAgentService.getAssistantAgentCapabilities)
      .mockImplementationOnce(() => new Promise((res) => { resolveFirst = res }))
      .mockImplementationOnce(() => new Promise((res) => { resolveSecond = res }))

    const { loading, capabilities, loadAssistantAgentCapabilities } =
      useGetAssistantAgentCapabilities()

    const call1 = loadAssistantAgentCapabilities()
    const call2 = loadAssistantAgentCapabilities()

    expect(loading.value).toBe(true)

    resolveFirst({ data: { capabilities: { web_search: false } } })
    await Promise.resolve()

    expect(capabilities.value).toEqual({})
    expect(loading.value).toBe(true)

    resolveSecond({ data: { capabilities: { web_search: true, code_exec: true } } })
    await Promise.all([call1, call2])

    expect(capabilities.value).toEqual({ web_search: true, code_exec: true })
    expect(loading.value).toBe(false)
  })
})
