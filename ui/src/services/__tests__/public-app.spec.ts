import { beforeEach, describe, expect, it, vi } from 'vitest'
import { sendPublicAppA2aMessage } from '@/services/public-app'
import * as request from '@/utils/request'

vi.mock('@/utils/request', () => ({ get: vi.fn(), post: vi.fn(), ssePost: vi.fn() }))

describe('public app service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('forwards an abort signal to streaming A2A requests', async () => {
    const controller = new AbortController()
    const onData = vi.fn()

    await sendPublicAppA2aMessage('app-1', 'hello', '', [], onData, controller.signal)

    expect(request.ssePost).toHaveBeenCalledWith(
      '/public/apps/app-1/a2a/messages',
      expect.objectContaining({ signal: controller.signal }),
      onData,
    )
  })
})
