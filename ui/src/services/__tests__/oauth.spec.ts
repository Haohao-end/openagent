import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authorize, provider } from '@/services/oauth'
import * as request from '@/utils/request'

vi.mock('@/utils/request', () => ({
  get: vi.fn(),
  post: vi.fn(),
}))

describe('oauth service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(request.get).mockResolvedValue({ data: {} } as never)
    vi.mocked(request.post).mockResolvedValue({ data: {} } as never)
  })

  it('loads provider redirect urls from provider-specific endpoints', async () => {
    await provider('github')

    expect(request.get).toHaveBeenCalledWith('/oauth/github')
  })

  it('posts authorize requests with the provider name, code, and intent', async () => {
    await authorize('google', 'oauth-code', 'login')

    expect(request.post).toHaveBeenCalledWith('/oauth/authorize/google', {
      body: {
        code: 'oauth-code',
        intent: 'login',
      },
    })
  })
})
