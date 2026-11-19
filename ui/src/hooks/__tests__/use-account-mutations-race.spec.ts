import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  useUpdateAvatar,
  useUpdateName,
  useUpdatePassword,
  useRevokeAccountSession,
} from '../use-account'
import * as accountService from '@/services/account'
import { Message } from '@arco-design/web-vue'

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@/stores/credential', () => ({
  useCredentialStore: () => ({ credential: { access_token: 'test' } }),
}))

const deferred = () => {
  let resolve!: (value: any) => void
  const promise = new Promise<any>((done) => { resolve = done })
  return { promise, resolve }
}

describe('use-account mutations race condition protection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps loading and ignores superseded updateAvatar completion', async () => {
    const p1 = deferred()
    const p2 = deferred()
    vi.spyOn(accountService, 'updateAvatar')
      .mockReturnValueOnce(p1.promise as any)
      .mockReturnValueOnce(p2.promise as any)

    const { loading, handleUpdateAvatar } = useUpdateAvatar()

    const req1 = handleUpdateAvatar('https://avatar1.png')
    const req2 = handleUpdateAvatar('https://avatar2.png')
    expect(loading.value).toBe(true)

    p2.resolve({ message: 'Avatar 2 updated' })
    const res2 = await req2
    expect(res2).toBe(true)
    expect(Message.success).toHaveBeenCalledWith('Avatar 2 updated')

    p1.resolve({ message: 'Avatar 1 updated' })
    const res1 = await req1
    expect(res1).toBe(false)
    expect(Message.success).toHaveBeenCalledTimes(1)
    expect(loading.value).toBe(false)
  })

  it('ignores superseded updatePassword completion', async () => {
    const p1 = deferred()
    const p2 = deferred()
    vi.spyOn(accountService, 'updatePassword')
      .mockReturnValueOnce(p1.promise as any)
      .mockReturnValueOnce(p2.promise as any)

    const { loading, handleUpdatePassword } = useUpdatePassword()

    const req1 = handleUpdatePassword('old1', 'new1')
    const req2 = handleUpdatePassword('old2', 'new2')
    expect(loading.value).toBe(true)

    p2.resolve({ message: 'Password 2 updated' })
    const res2 = await req2
    expect(res2).toBe(true)

    p1.resolve({ message: 'Password 1 updated' })
    const res1 = await req1
    expect(res1).toBe(false)
    expect(loading.value).toBe(false)
  })

  it('ignores superseded updateName completion', async () => {
    const p1 = deferred()
    const p2 = deferred()
    vi.spyOn(accountService, 'updateName')
      .mockReturnValueOnce(p1.promise as any)
      .mockReturnValueOnce(p2.promise as any)

    const { loading, handleUpdateName } = useUpdateName()

    const req1 = handleUpdateName('Name 1')
    const req2 = handleUpdateName('Name 2')
    expect(loading.value).toBe(true)

    p2.resolve({ data: { name: 'Name 2' } })
    const res2 = await req2
    expect(res2).toEqual({ data: { name: 'Name 2' } })

    p1.resolve({ data: { name: 'Name 1' } })
    const res1 = await req1
    expect(res1).toBe(false)
    expect(loading.value).toBe(false)
  })

  it('ignores superseded revokeAccountSession', async () => {
    const p1 = deferred()
    const p2 = deferred()
    vi.spyOn(accountService, 'revokeAccountSession')
      .mockReturnValueOnce(p1.promise as any)
      .mockReturnValueOnce(p2.promise as any)

    const { loading, handleRevokeAccountSession } = useRevokeAccountSession()

    const req1 = handleRevokeAccountSession('session-1')
    const req2 = handleRevokeAccountSession('session-2')
    expect(loading.value).toBe(true)

    p2.resolve({ message: 'Revoked 2' })
    const res2 = await req2
    expect(res2).toBe(true)

    p1.resolve({ message: 'Revoked 1' })
    const res1 = await req1
    expect(res1).toBe(false)
    expect(loading.value).toBe(false)
  })
})
