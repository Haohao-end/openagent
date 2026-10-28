import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ getAccountLoginHistory: vi.fn() }))
vi.mock('@/services/account', async importOriginal => ({
  ...await importOriginal<typeof import('@/services/account')>(),
  getAccountLoginHistory: mocks.getAccountLoginHistory,
}))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn() } }))

import { useGetAccountLoginHistory } from '@/hooks/use-account'

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
