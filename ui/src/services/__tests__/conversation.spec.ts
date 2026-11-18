import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getMessageTrace } from '@/services/conversation'
import * as request from '@/utils/request'

vi.mock('@/utils/request', () => ({
  get: vi.fn(),
  post: vi.fn(),
}))

describe('conversation service message trace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(request.get).mockResolvedValue({
      code: 'success',
      data: {
        message_id: 'msg-1',
        conversation_id: 'conv-1',
        app_id: 'app-1',
        status: 'normal',
        error: '',
        latency: 1.2,
        total_token_count: 150,
        total_price: 0.03,
        created_at: 1700000000,
        timeline: [],
      },
    } as never)
  })

  it('fetches message trace timeline details by message id', async () => {
    const result = await getMessageTrace('msg-1')

    expect(request.get).toHaveBeenCalledWith('/conversations/messages/msg-1/trace')
    expect(result.data.message_id).toBe('msg-1')
  })
})
