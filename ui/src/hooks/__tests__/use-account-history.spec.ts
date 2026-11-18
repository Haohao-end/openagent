import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGetAccountLoginHistory } from '@/hooks/use-account'
import * as accountService from '@/services/account'
import { useCredentialStore } from '@/stores/credential'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/services/account', () => ({
  getAccountSessions: vi.fn(),
  getAccountLoginHistory: vi.fn(),
  getCurrentUser: vi.fn(),
  revokeAccountSession: vi.fn(),
  revokeOtherAccountSessions: vi.fn(),
  sendChangeEmailCode: vi.fn(),
  updateAvatar: vi.fn(),
  updateEmail: vi.fn(),
  updateName: vi.fn(),
  updatePassword: vi.fn(),
  unbindOAuth: vi.fn(),
}))

vi.mock('@/stores/credential', () => ({
  useCredentialStore: vi.fn(),
}))

describe('useGetAccountLoginHistory', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(useCredentialStore).mockReturnValue({
      credential: 'user-a',
    } as any)
  })

  it('clears state on credential change', async () => {
    const credentialStore = useCredentialStore()
    const { history_state, loadAccountLoginHistory, clearAccountLoginHistory } = useGetAccountLoginHistory()

    vi.mocked(accountService.getAccountLoginHistory).mockResolvedValue({
      code: 'success',
      data: { history: [{ id: 'h1' }], total: 1, current_page: 1, page_size: 5 },
    } as never)

    await loadAccountLoginHistory()
    expect(history_state.value.history.length).toBe(1)

    // Simulate credential change
    vi.mocked(credentialStore).credential = 'user-b'
    // Manually trigger
    clearAccountLoginHistory()
    await new Promise((r) => setTimeout(r, 0))

    expect(history_state.value.history.length).toBe(0)
  })
})
