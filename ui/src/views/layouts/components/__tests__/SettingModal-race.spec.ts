import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createTestI18n } from '@/i18n'
import SettingModal from '../SettingModal.vue'

const mocks = vi.hoisted(() => ({
  loadSessions: vi.fn(),
  loadHistory: vi.fn(),
}))

vi.mock('@/stores/account', () => ({
  useAccountStore: () => ({
    account: { id: 'account', name: 'User', avatar: '', email: '', oauth_bindings: [], password_set: true },
    update: vi.fn(),
  }),
}))

vi.mock('@/services/account', () => ({
  getAccountSessions: mocks.loadSessions,
  getAccountLoginHistory: mocks.loadHistory,
}))

const deferred = () => {
  let reject!: (error: Error) => void
  const promise = new Promise<void>((_resolve, rejectPromise) => {
    reject = rejectPromise
  })
  return { promise, reject }
}

describe('SettingModal device request ordering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores an older device request failure after a newer load succeeds', async () => {
    const staleRequest = deferred()
    mocks.loadSessions.mockResolvedValue({ data: { sessions: [], session_capable: true } })
    mocks.loadHistory
      .mockReturnValueOnce(staleRequest.promise)
      .mockResolvedValueOnce({
        data: {
          history: [{ id: 'newest', device_name: 'Newest device', status: 'active', created_at: 0 }],
          total: 1,
          current_page: 1,
          page_size: 5,
        },
      })
    const wrapper = shallowMount(SettingModal, {
      props: { visible: true, initialTab: 'devices' },
      global: {
        plugins: [createTestI18n()],
        stubs: { 'a-modal': { template: '<div><slot /></div>' } },
      },
    })
    const { handleHistoryStatusChange } = (
      wrapper.vm.$ as unknown as {
        setupState: { handleHistoryStatusChange: (value: string | number | boolean) => Promise<void> }
      }
    ).setupState

    await handleHistoryStatusChange('active')
    staleRequest.reject(new Error('Old device request failed'))
    await flushPromises()

    expect(wrapper.text()).toContain('Newest device')
    expect(wrapper.text()).not.toContain('Old device request failed')
    wrapper.unmount()
  })
})
