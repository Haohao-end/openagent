import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ getAccountLoginHistory: vi.fn(), getAccountSessions: vi.fn() }))
vi.mock('@/services/account', async importOriginal => ({
  ...await importOriginal<typeof import('@/services/account')>(),
  getAccountLoginHistory: mocks.getAccountLoginHistory,
  getAccountSessions: mocks.getAccountSessions,
}))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn() } }))

import { useGetAccountLoginHistory, useGetAccountSessions } from '@/hooks/use-account'

const deferred = () => {
  let resolve!: (value: any) => void
  const promise = new Promise<any>(done => { resolve = done })
  return { promise, resolve }
}

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
