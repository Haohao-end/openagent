import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  usePasswordLogin,
  useVerifyRegister,
  useVerifyLoginChallenge,
  useLogout,
} from '../use-auth'
import * as authService from '@/services/auth'
import { Message } from '@arco-design/web-vue'

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const deferred = () => {
  let resolve!: (value: any) => void
  const promise = new Promise<any>((done) => { resolve = done })
  return { promise, resolve }
}

describe('use-auth race condition protection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps the latest password login authorization when earlier attempt resolves last', async () => {
    const p1 = deferred()
    const p2 = deferred()
    vi.spyOn(authService, 'passwordLogin')
      .mockReturnValueOnce(p1.promise as any)
      .mockReturnValueOnce(p2.promise as any)

    const { loading, authorization, handlePasswordLogin } = usePasswordLogin()

    const req1 = handlePasswordLogin('u1@example.com', 'pwd1')
    const req2 = handlePasswordLogin('u2@example.com', 'pwd2')
    expect(loading.value).toBe(true)

    p2.resolve({ data: { access_token: 'token-2' } })
    await req2
    expect(authorization.value).toEqual({ access_token: 'token-2' })

    p1.resolve({ data: { access_token: 'token-1' } })
    await req1
    expect(authorization.value).toEqual({ access_token: 'token-2' })
    expect(loading.value).toBe(false)
  })

  it('keeps the latest verifyRegister authorization when earlier attempt resolves last', async () => {
    const p1 = deferred()
    const p2 = deferred()
    vi.spyOn(authService, 'verifyRegister')
      .mockReturnValueOnce(p1.promise as any)
      .mockReturnValueOnce(p2.promise as any)

    const { loading, authorization, handleVerifyRegister } = useVerifyRegister()

    const req1 = handleVerifyRegister('u1@example.com', 'pwd1', '111111')
    const req2 = handleVerifyRegister('u2@example.com', 'pwd2', '222222')

    p2.resolve({ data: { access_token: 'token-reg-2' } })
    await req2
    expect(authorization.value).toEqual({ access_token: 'token-reg-2' })

    p1.resolve({ data: { access_token: 'token-reg-1' } })
    await req1
    expect(authorization.value).toEqual({ access_token: 'token-reg-2' })
    expect(loading.value).toBe(false)
  })

  it('keeps the latest verifyLoginChallenge authorization', async () => {
    const p1 = deferred()
    const p2 = deferred()
    vi.spyOn(authService, 'verifyLoginChallenge')
      .mockReturnValueOnce(p1.promise as any)
      .mockReturnValueOnce(p2.promise as any)

    const { loading, authorization, handleVerifyLoginChallenge } = useVerifyLoginChallenge()

    const req1 = handleVerifyLoginChallenge('ch-1', '111111')
    const req2 = handleVerifyLoginChallenge('ch-2', '222222')

    p2.resolve({ data: { access_token: 'token-ch-2' } })
    await req2
    expect(authorization.value).toEqual({ access_token: 'token-ch-2' })

    p1.resolve({ data: { access_token: 'token-ch-1' } })
    await req1
    expect(authorization.value).toEqual({ access_token: 'token-ch-2' })
    expect(loading.value).toBe(false)
  })

  it('ignores superseded logout resolution', async () => {
    const p1 = deferred()
    const p2 = deferred()
    vi.spyOn(authService, 'logout')
      .mockReturnValueOnce(p1.promise as any)
      .mockReturnValueOnce(p2.promise as any)

    const { loading, handleLogout } = useLogout()

    const req1 = handleLogout()
    const req2 = handleLogout()

    p2.resolve({ message: 'Logout 2' })
    await req2
    expect(Message.success).toHaveBeenCalledWith('Logout 2')

    p1.resolve({ message: 'Logout 1' })
    await req1
    expect(Message.success).toHaveBeenCalledTimes(1)
    expect(loading.value).toBe(false)
  })
})
