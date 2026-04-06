import { beforeEach, describe, expect, it, vi } from 'vitest'

import { deleteConversation, searchConversations, updateConversationName } from '@/services/conversation-search'
import * as request from '@/utils/request'

vi.mock('@/utils/request', () => ({
  get: vi.fn(),
  post: vi.fn(),
}))

describe('conversation-search service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(request.get).mockResolvedValue({ data: [] } as never)
    vi.mocked(request.post).mockResolvedValue({ message: 'ok' } as never)
  })

  it('requests search results with the default limit', async () => {
    await searchConversations('python')

    expect(request.get).toHaveBeenCalledWith('/conversations/search', {
      params: {
        query: 'python',
        limit: 50,
      },
    })
  })

  it('posts conversation delete requests to the expected endpoint', async () => {
    await deleteConversation('conversation-1')

    expect(request.post).toHaveBeenCalledWith('/conversations/conversation-1/delete')
  })

  it('posts rename requests with the new conversation name', async () => {
    await updateConversationName('conversation-1', '新的标题')

    expect(request.post).toHaveBeenCalledWith('/conversations/conversation-1/name', {
      body: {
        name: '新的标题',
      },
    })
  })
})
