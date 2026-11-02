import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getAccountLoginHistory: vi.fn(),
  getAccountSessions: vi.fn(),
  getCurrentUser: vi.fn(),
  credentialStore: { credential: { access_token: 'user-a' } },
}))
vi.mock('@/services/account', async importOriginal => ({
  ...await importOriginal<typeof import('@/services/account')>(),
  getAccountLoginHistory: mocks.getAccountLoginHistory,
  getAccountSessions: mocks.getAccountSessions,
  getCurrentUser: mocks.getCurrentUser,
}))
vi.mock('@/stores/credential', () => ({ useCredentialStore: () => mocks.credentialStore }))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn() } }))

import { useGetAccountLoginHistory, useGetAccountSessions, useGetCurrentUser } from '@/hooks/use-account'

const deferred = () => {
  let resolve!: (value: any) => void
  let reject!: (error: Error) => void
  const promise = new Promise<any>((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}

describe('useGetCurrentUser', () => {
  it('ignores a user response that resolves after logout', async () => {
    const request = deferred()
    mocks.credentialStore.credential = { access_token: 'user-a' }
    mocks.getCurrentUser.mockReturnValueOnce(request.promise)
    const { current_user, loadCurrentUser } = useGetCurrentUser()
    const pending = loadCurrentUser()
    mocks.credentialStore.credential = { access_token: '' }
    request.resolve({ data: { id: 'user-a' } })
    await pending

    expect(current_user.value).toEqual({})
  })

  it('ignores a user request error that arrives after logout', async () => {
    const request = deferred()
    mocks.credentialStore.credential = { access_token: 'user-a' }
    mocks.getCurrentUser.mockReturnValueOnce(request.promise)
    const { current_user, loadCurrentUser } = useGetCurrentUser()
    const pending = loadCurrentUser()
    mocks.credentialStore.credential = { access_token: '' }
    request.reject(new Error('expired user request'))

    await expect(pending).resolves.toBeUndefined()
    expect(current_user.value).toEqual({})
  })
})

describe('useGetAccountLoginHistory', () => {
  it('keeps the newest filter result when an older request finishes last', async () => {
    const older = deferred()
    const newer = deferred()
    mocks.getAccountLoginHistory.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    const { loading, history_state, loadAccountLoginHistory } = useGetAccountLoginHistory()
    const oldRequest = loadAccountLoginHistory({ search: 'old' })
    const newRequest = loadAccountLoginHistory({ search: 'new' })
    newer.resolve({ data: { history: [{ search: 'new' }], total: 1, current_page: 1, page_size: 5 } })
    await newRequest
    older.resolve({ data: { history: [{ search: 'old' }], total: 1, current_page: 1, page_size: 5 } })
    await oldRequest

    expect(history_state.value.history).toEqual([{ search: 'new' }])
    expect(loading.value).toBe(false)
  })
})

describe('useGetAccountSessions', () => {
  it('keeps the latest session list when an older request resolves after revocation', async () => {
    const older = deferred()
    const newer = deferred()
    mocks.getAccountSessions.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    const { session_state, loadAccountSessions } = useGetAccountSessions()
    const oldRequest = loadAccountSessions()
    const newRequest = loadAccountSessions()
    newer.resolve({ data: { sessions: [], session_capable: true, current_session_id: null } })
    await newRequest
    older.resolve({ data: { sessions: [{ id: 'revoked-session' }], session_capable: true, current_session_id: null } })
    await oldRequest

    expect(session_state.value.sessions).toEqual([])
  })

  it('keeps loading while a newer session request is still pending', async () => {
    const older = deferred()
    const newer = deferred()
    mocks.getAccountSessions.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    const { loading, loadAccountSessions } = useGetAccountSessions()
    const oldRequest = loadAccountSessions()
    const newRequest = loadAccountSessions()
    older.resolve({ data: { sessions: [], session_capable: true, current_session_id: null } })
    await oldRequest

    expect(loading.value).toBe(true)
    newer.resolve({ data: { sessions: [], session_capable: true, current_session_id: null } })
    await newRequest
    expect(loading.value).toBe(false)
  })
})
