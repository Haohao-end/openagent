import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getAccountLoginHistory,
  getAccountSessions,
  getCurrentUser,
  revokeAccountSession,
  revokeOtherAccountSessions,
  sendChangeEmailCode,
  unbindOAuth,
  updateAvatar,
  updateEmail,
  updateName,
  updatePassword,
} from '@/services/account'
import * as request from '@/utils/request'

vi.mock('@/utils/request', () => ({
  get: vi.fn(),
  post: vi.fn(),
}))

describe('account service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(request.get).mockResolvedValue({ data: {} } as never)
    vi.mocked(request.post).mockResolvedValue({ message: 'ok' } as never)
  })

  it('loads current user profile from the account endpoint', async () => {
    await getCurrentUser()

    expect(request.get).toHaveBeenCalledWith('/account')
  })

  it('posts password updates with current and new password', async () => {
    await updatePassword('OldPass123', 'NewPass123')

    expect(request.post).toHaveBeenCalledWith('/account/password', {
      body: {
        current_password: 'OldPass123',
        new_password: 'NewPass123',
      },
    })
  })

  it('posts name and avatar updates to their expected endpoints', async () => {
    await updateName('新昵称')
    await updateAvatar('https://img.example.com/avatar.png')

    expect(request.post).toHaveBeenNthCalledWith(1, '/account/name', {
      body: { name: '新昵称' },
    })
    expect(request.post).toHaveBeenNthCalledWith(2, '/account/avatar', {
      body: { avatar: 'https://img.example.com/avatar.png' },
    })
  })

  it('posts email verification and update requests to the expected endpoints', async () => {
    await sendChangeEmailCode('next@example.com')
    await updateEmail('next@example.com', '123456', 'OldPass123')

    expect(request.post).toHaveBeenNthCalledWith(1, '/account/email/send-code', {
      body: { email: 'next@example.com' },
    })
    expect(request.post).toHaveBeenNthCalledWith(2, '/account/email', {
      body: { email: 'next@example.com', code: '123456', current_password: 'OldPass123' },
    })
  })

  it('loads and revokes account sessions from the expected endpoints', async () => {
    await getAccountSessions()
    await getAccountLoginHistory()
    await revokeAccountSession('session-1')
    await revokeOtherAccountSessions()

    expect(request.get).toHaveBeenCalledWith('/account/sessions')
    expect(request.get).toHaveBeenCalledWith('/account/login-history', {
      params: undefined,
    })
    expect(request.post).toHaveBeenNthCalledWith(1, '/account/sessions/session-1/revoke')
    expect(request.post).toHaveBeenNthCalledWith(2, '/account/sessions/revoke-others')
  })

  it('posts provider unbind requests to the provider-specific endpoint', async () => {
    await unbindOAuth('github')

    expect(request.post).toHaveBeenCalledWith('/account/oauth/github/unbind')
  })
})
