import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  passwordLogin,
  prepareRegister,
  resendLoginChallenge,
  resetPassword,
  sendResetCode,
  verifyLoginChallenge,
  verifyRegister,
} from '@/services/auth'
import * as request from '@/utils/request'

vi.mock('@/utils/request', () => ({
  post: vi.fn(),
}))

describe('auth service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(request.post).mockResolvedValue({ data: {}, message: 'ok' } as never)
  })

  it('posts password login credentials to the auth endpoint', async () => {
    await passwordLogin('tester@example.com', 'Abcd1234')

    expect(request.post).toHaveBeenCalledWith('/auth/password-login', {
      body: {
        email: 'tester@example.com',
        password: 'Abcd1234',
      },
    })
  })

  it('posts register prepare and verify requests to the expected endpoints', async () => {
    await prepareRegister('tester@example.com', 'Abcd1234')
    await verifyRegister('tester@example.com', 'Abcd1234', '123456')

    expect(request.post).toHaveBeenNthCalledWith(1, '/auth/register/prepare', {
      body: {
        email: 'tester@example.com',
        password: 'Abcd1234',
      },
    })
    expect(request.post).toHaveBeenNthCalledWith(2, '/auth/register/verify', {
      body: {
        email: 'tester@example.com',
        password: 'Abcd1234',
        code: '123456',
      },
    })
  })

  it('posts reset-password requests to the expected endpoints', async () => {
    await sendResetCode('tester@example.com')
    await resetPassword('tester@example.com', '123456', 'NewPass123')

    expect(request.post).toHaveBeenNthCalledWith(1, '/auth/send-reset-code', {
      body: { email: 'tester@example.com' },
    })
    expect(request.post).toHaveBeenNthCalledWith(2, '/auth/reset-password', {
      body: {
        email: 'tester@example.com',
        code: '123456',
        new_password: 'NewPass123',
      },
    })
  })

  it('posts login challenge verify and resend requests to the expected endpoints', async () => {
    await verifyLoginChallenge('challenge-1', '654321')
    await resendLoginChallenge('challenge-1')

    expect(request.post).toHaveBeenNthCalledWith(1, '/auth/login-challenge/verify', {
      body: {
        challenge_id: 'challenge-1',
        code: '654321',
      },
    })
    expect(request.post).toHaveBeenNthCalledWith(2, '/auth/login-challenge/resend', {
      body: {
        challenge_id: 'challenge-1',
      },
    })
  })
})
