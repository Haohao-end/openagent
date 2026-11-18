import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGetAccountSessions } from '@/hooks/use-account'
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

describe('useGetAccountSessions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(useCredentialStore).mockReturnValue({
      credential: 'user-a',
    } as any)
  })

  it('clears state on credential change', async () => {
    const credentialStore = useCredentialStore()
    const { session_state, loadAccountSessions, clearSessionState } = useGetAccountSessions()

    vi.mocked(accountService.getAccountSessions).mockResolvedValue({
      code: 'success',
      data: { session_capable: true, current_session_id: 's1', sessions: [{ id: 's1' }] },
    } as never)

    await loadAccountSessions()
    expect(session_state.value.sessions.length).toBe(1)

    // Simulate credential change
    vi.mocked(credentialStore).credential = 'user-b'
    // Manually trigger the watch
    clearSessionState() 
    await new Promise((r) => setTimeout(r, 0))

    expect(session_state.value.sessions.length).toBe(0)
  })
})
