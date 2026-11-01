import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useGetAssistantAgentMessagesWithPage } from '@/hooks/use-assistant-agent'
import {
  useGetConversationMessagesWithPage,
  useGetConversationName,
  useGetRecentConversations,
} from '@/hooks/use-conversation'
import { useGetDebugConversationMessagesWithPage } from '@/hooks/use-app'
import * as assistantAgentService from '@/services/assistant-agent'
import * as appService from '@/services/app'
import * as conversationService from '@/services/conversation'

vi.mock('@/services/app', async () => {
  const actual = await vi.importActual<typeof import('@/services/app')>('@/services/app')
  return {
    ...actual,
    getDebugConversationMessagesWithPage: vi.fn(),
  }
})

vi.mock('@/services/conversation', async () => {
  const actual = await vi.importActual<typeof import('@/services/conversation')>(
    '@/services/conversation',
  )
  return {
    ...actual,
    getConversationMessages: vi.fn(),
    getConversationName: vi.fn(),
    getRecentConversations: vi.fn(),
  }
})

vi.mock('@/services/assistant-agent', async () => {
  const actual = await vi.importActual<typeof import('@/services/assistant-agent')>(
    '@/services/assistant-agent',
  )
  return {
    ...actual,
    getAssistantAgentMessagesWithPage: vi.fn(),
  }
})

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
  Modal: {
    warning: vi.fn(),
  },
}))

type PagedMessage = {
  id: string
  conversation_id: string
  query: string
  image_urls: string[]
  input_parts: Array<Record<string, any>>
  answer: string
  answer_parts: Array<Record<string, any>>
  artifacts: Array<Record<string, any>>
  total_token_count: number
  latency: number
  agent_thoughts: Array<Record<string, any>>
  suggested_questions: string[]
  created_at: number
}

type PaginatorResponse = {
  current_page: number
  page_size: number
  total_page: number
  total_record: number
}

const buildMessage = (id: string, created_at: number): PagedMessage => ({
  id,
  conversation_id: 'conversation-1',
  query: `query-${id}`,
  image_urls: [],
  input_parts: [],
  answer: `answer-${id}`,
  answer_parts: [{ type: 'text', text: `answer-${id}` }],
  artifacts: [],
  total_token_count: 1,
  latency: 1,
  agent_thoughts: [],
  suggested_questions: [],
  created_at,
})

const buildPage = (list: PagedMessage[], paginator: PaginatorResponse) => ({
  data: {
    list,
    paginator,
  },
})

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

describe('historical chat pagination', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps the debug conversation cursor fixed after the first page', async () => {
    vi.mocked(appService.getDebugConversationMessagesWithPage)
      .mockResolvedValueOnce(
        buildPage(
          [buildMessage('debug-latest-2', 200), buildMessage('debug-latest-1', 100)],
          { current_page: 1, page_size: 5, total_page: 2, total_record: 4 },
        ) as never,
      )
      .mockResolvedValueOnce(
        buildPage(
          [buildMessage('debug-older-2', 80), buildMessage('debug-older-1', 60)],
          { current_page: 2, page_size: 5, total_page: 2, total_record: 4 },
        ) as never,
      )

    const { messages, loadDebugConversationMessages } = useGetDebugConversationMessagesWithPage()

    await loadDebugConversationMessages('app-1', true, 'conversation-1')
    await loadDebugConversationMessages('app-1', false, 'conversation-1')

    expect(appService.getDebugConversationMessagesWithPage).toHaveBeenNthCalledWith(
      1,
      'app-1',
      {
        current_page: 1,
        page_size: 5,
        created_at: 0,
        conversation_id: 'conversation-1',
      },
    )
    expect(appService.getDebugConversationMessagesWithPage).toHaveBeenNthCalledWith(
      2,
      'app-1',
      {
        current_page: 2,
        page_size: 5,
        created_at: 200,
        conversation_id: 'conversation-1',
      },
    )
    expect(messages.value.map((item) => item.id)).toEqual([
      'debug-latest-2',
      'debug-latest-1',
      'debug-older-2',
      'debug-older-1',
    ])
    expect(messages.value.map((item) => item.render_id)).toEqual([
      'debug-latest-2',
      'debug-latest-1',
      'debug-older-2',
      'debug-older-1',
    ])
  })

  it('ignores an older debug conversation response after switching conversations', async () => {
    const olderResponse = createDeferred<ReturnType<typeof buildPage>>()
    const newerResponse = createDeferred<ReturnType<typeof buildPage>>()
    vi.mocked(appService.getDebugConversationMessagesWithPage)
      .mockReturnValueOnce(olderResponse.promise as never)
      .mockReturnValueOnce(newerResponse.promise as never)
    const { messages, loadDebugConversationMessages } = useGetDebugConversationMessagesWithPage()

    const olderRequest = loadDebugConversationMessages('app-1', true, 'conversation-old')
    const newerRequest = loadDebugConversationMessages('app-1', true, 'conversation-new')
    newerResponse.resolve(buildPage([buildMessage('debug-new', 200)], {
      current_page: 1, page_size: 5, total_page: 1, total_record: 1,
    }))
    await newerRequest
    olderResponse.resolve(buildPage([buildMessage('debug-old', 100)], {
      current_page: 1, page_size: 5, total_page: 1, total_record: 1,
    }))
    await olderRequest

    expect(messages.value.map((message) => message.id)).toEqual(['debug-new'])
  })

  it('deduplicates overlapping debug history pages by message id', async () => {
    vi.mocked(appService.getDebugConversationMessagesWithPage)
      .mockResolvedValueOnce(
        buildPage(
          [buildMessage('debug-latest-2', 200), buildMessage('debug-latest-1', 100)],
          { current_page: 1, page_size: 5, total_page: 2, total_record: 3 },
        ) as never,
      )
      .mockResolvedValueOnce(
        buildPage(
          [buildMessage('debug-latest-1', 100), buildMessage('debug-older-1', 60)],
          { current_page: 2, page_size: 5, total_page: 2, total_record: 3 },
        ) as never,
      )

    const { messages, loadDebugConversationMessages } = useGetDebugConversationMessagesWithPage()

    await loadDebugConversationMessages('app-1', true, 'conversation-1')
    await loadDebugConversationMessages('app-1', false, 'conversation-1')

    expect(messages.value.map((item) => item.id)).toEqual([
      'debug-latest-2',
      'debug-latest-1',
      'debug-older-1',
    ])
    expect(messages.value.map((item) => item.render_id)).toEqual([
      'debug-latest-2',
      'debug-latest-1',
      'debug-older-1',
    ])
  })

  it('keeps the conversation cursor fixed after the first page', async () => {
    vi.mocked(conversationService.getConversationMessages)
      .mockResolvedValueOnce(
        buildPage(
          [buildMessage('conversation-latest-2', 300), buildMessage('conversation-latest-1', 200)],
          { current_page: 1, page_size: 5, total_page: 2, total_record: 4 },
        ) as never,
      )
      .mockResolvedValueOnce(
        buildPage(
          [buildMessage('conversation-older-2', 180), buildMessage('conversation-older-1', 160)],
          { current_page: 2, page_size: 5, total_page: 2, total_record: 4 },
        ) as never,
      )

    const { messages, loadConversationMessagesWithPage } = useGetConversationMessagesWithPage()

    await loadConversationMessagesWithPage('conversation-1', true)
    await loadConversationMessagesWithPage('conversation-1', false)

    expect(conversationService.getConversationMessages).toHaveBeenNthCalledWith(
      1,
      'conversation-1',
      {
        current_page: 1,
        page_size: 5,
        created_at: 0,
      },
    )
    expect(conversationService.getConversationMessages).toHaveBeenNthCalledWith(
      2,
      'conversation-1',
      {
        current_page: 2,
        page_size: 5,
        created_at: 300,
      },
    )
    expect(messages.value.map((item) => item.id)).toEqual([
      'conversation-latest-2',
      'conversation-latest-1',
      'conversation-older-2',
      'conversation-older-1',
    ])
  })

  it('ignores an older conversation response after switching conversations', async () => {
    const olderResponse = createDeferred<ReturnType<typeof buildPage>>()
    const newerResponse = createDeferred<ReturnType<typeof buildPage>>()
    vi.mocked(conversationService.getConversationMessages)
      .mockReturnValueOnce(olderResponse.promise as never)
      .mockReturnValueOnce(newerResponse.promise as never)
    const { messages, loadConversationMessagesWithPage } = useGetConversationMessagesWithPage()

    const olderRequest = loadConversationMessagesWithPage('conversation-old', true)
    const newerRequest = loadConversationMessagesWithPage('conversation-new', true)
    newerResponse.resolve(buildPage([buildMessage('new', 200)], {
      current_page: 1, page_size: 5, total_page: 1, total_record: 1,
    }))
    await newerRequest
    olderResponse.resolve(buildPage([buildMessage('old', 100)], {
      current_page: 1, page_size: 5, total_page: 1, total_record: 1,
    }))
    await olderRequest

    expect(messages.value.map((message) => message.id)).toEqual(['new'])
  })

  it('ignores recent conversations from before logout without clearing current loading', async () => {
    const olderResponse = createDeferred<{ data: Array<{ id: string }> }>()
    const newerResponse = createDeferred<{ data: Array<{ id: string }> }>()
    vi.mocked(conversationService.getRecentConversations)
      .mockReturnValueOnce(olderResponse.promise as never)
      .mockReturnValueOnce(newerResponse.promise as never)
    const hook = useGetRecentConversations()
    const olderRequest = hook.loadRecentConversations()
    hook.invalidateRecentConversations()
    hook.conversations.value = []
    const newerRequest = hook.loadRecentConversations()

    olderResponse.resolve({ data: [{ id: 'private-before-logout' }] })
    await olderRequest
    expect(hook.conversations.value).toEqual([])
    expect(hook.loading.value).toBe(true)
    newerResponse.resolve({ data: [{ id: 'new-session' }] })
    await newerRequest
    expect(hook.conversations.value.map(({ id }) => id)).toEqual(['new-session'])
    expect(hook.loading.value).toBe(false)
  })

  it('ignores an older conversation name response after switching conversations', async () => {
    const olderResponse = createDeferred<{ data: { name: string } }>()
    const newerResponse = createDeferred<{ data: { name: string } }>()
    vi.mocked(conversationService.getConversationName)
      .mockReturnValueOnce(olderResponse.promise as never)
      .mockReturnValueOnce(newerResponse.promise as never)
    const { name, loadConversationName } = useGetConversationName()

    const olderRequest = loadConversationName('conversation-old')
    const newerRequest = loadConversationName('conversation-new')
    newerResponse.resolve({ data: { name: 'new conversation' } })
    await newerRequest
    olderResponse.resolve({ data: { name: 'old conversation' } })
    await olderRequest

    expect(name.value).toBe('new conversation')
  })

  it('keeps the assistant agent cursor fixed after the first page', async () => {
    vi.mocked(assistantAgentService.getAssistantAgentMessagesWithPage)
      .mockResolvedValueOnce(
        buildPage(
          [buildMessage('assistant-latest-2', 400), buildMessage('assistant-latest-1', 350)],
          { current_page: 1, page_size: 20, total_page: 2, total_record: 4 },
        ) as never,
      )
      .mockResolvedValueOnce(
        buildPage(
          [buildMessage('assistant-older-2', 280), buildMessage('assistant-older-1', 260)],
          { current_page: 2, page_size: 20, total_page: 2, total_record: 4 },
        ) as never,
      )

    const { messages, loadAssistantAgentMessages } = useGetAssistantAgentMessagesWithPage()

    await loadAssistantAgentMessages(true, 'conversation-1')
    await loadAssistantAgentMessages(false, 'conversation-1')

    expect(assistantAgentService.getAssistantAgentMessagesWithPage).toHaveBeenNthCalledWith(
      1,
      {
        current_page: 1,
        page_size: 20,
        created_at: 0,
        conversation_id: 'conversation-1',
      },
    )
    expect(assistantAgentService.getAssistantAgentMessagesWithPage).toHaveBeenNthCalledWith(
      2,
      {
        current_page: 2,
        page_size: 20,
        created_at: 400,
        conversation_id: 'conversation-1',
      },
    )
    expect(messages.value.map((item) => item.id)).toEqual([
      'assistant-latest-2',
      'assistant-latest-1',
      'assistant-older-2',
      'assistant-older-1',
    ])
  })

  it('ignores an older assistant-agent response after switching conversations', async () => {
    const olderResponse = createDeferred<ReturnType<typeof buildPage>>()
    const newerResponse = createDeferred<ReturnType<typeof buildPage>>()
    vi.mocked(assistantAgentService.getAssistantAgentMessagesWithPage)
      .mockReturnValueOnce(olderResponse.promise as never)
      .mockReturnValueOnce(newerResponse.promise as never)
    const { messages, loadAssistantAgentMessages } = useGetAssistantAgentMessagesWithPage()

    const olderRequest = loadAssistantAgentMessages(true, 'conversation-old')
    const newerRequest = loadAssistantAgentMessages(true, 'conversation-new')
    newerResponse.resolve(buildPage([buildMessage('agent-new', 200)], {
      current_page: 1, page_size: 20, total_page: 1, total_record: 1,
    }))
    await newerRequest
    olderResponse.resolve(buildPage([buildMessage('agent-old', 100)], {
      current_page: 1, page_size: 20, total_page: 1, total_record: 1,
    }))
    await olderRequest

    expect(messages.value.map((message) => message.id)).toEqual(['agent-new'])
  })

  it('does not restore assistant history after logout clears messages', async () => {
    const pendingResponse = createDeferred<ReturnType<typeof buildPage>>()
    vi.mocked(assistantAgentService.getAssistantAgentMessagesWithPage)
      .mockReturnValueOnce(pendingResponse.promise as never)
    const {
      messages,
      loadAssistantAgentMessages,
      invalidateAssistantAgentMessages,
    } = useGetAssistantAgentMessagesWithPage()

    const pendingRequest = loadAssistantAgentMessages(true, 'conversation-private')
    invalidateAssistantAgentMessages()
    messages.value = []
    pendingResponse.resolve(buildPage([buildMessage('private-message', 100)], {
      current_page: 1, page_size: 20, total_page: 1, total_record: 1,
    }))
    await pendingRequest

    expect(messages.value).toEqual([])
  })
})
