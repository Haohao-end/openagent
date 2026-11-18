import { beforeEach, describe, expect, it, vi } from 'vitest'

import { compareMessages } from '@/services/conversation'
import * as request from '@/utils/request'

vi.mock('@/utils/request', () => ({
  get: vi.fn(),
  post: vi.fn(),
}))

describe('conversation compare service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(request.post).mockResolvedValue({
      code: 'success',
      data: {
        target: {
          id: 'target-1',
          status: 'normal',
          error: '',
          latency: 2.1,
          total_token_count: 120,
          total_price: 0.02,
          answer_length: 50,
        },
        base: {
          id: 'base-1',
          status: 'error',
          error: 'timeout',
          latency: 1.0,
          total_token_count: 80,
          total_price: 0.01,
          answer_length: 20,
        },
        diff: {
          latency_diff: 1.1,
          total_token_count_diff: 40,
          message_token_count_diff: 15,
          answer_token_count_diff: 25,
          total_price_diff: 0.01,
          status_changed: true,
          error_changed: true,
          answer_match: false,
          answer_length_diff: 30,
        },
      },
    } as never)
  })

  it('posts comparison request with target and base message ids', async () => {
    const payload = {
      target_message_id: 'target-1',
      base_message_id: 'base-1',
    }
    const result = await compareMessages(payload)

    expect(request.post).toHaveBeenCalledWith('/conversations/messages/compare', {
      body: payload,
    })
    expect(result.data.diff.status_changed).toBe(true)
    expect(result.data.diff.latency_diff).toBe(1.1)
  })
})
