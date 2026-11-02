import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { createTestI18n } from '@/i18n'
import SettingModal from '../SettingModal.vue'

const mocks = vi.hoisted(() => ({
  loadSessions: vi.fn(),
  loadHistory: vi.fn(),
  getCurrentUser: vi.fn(),
  updateAvatar: vi.fn(),
  uploadImage: vi.fn(),
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
  getCurrentUser: mocks.getCurrentUser,
  updateAvatar: mocks.updateAvatar,
}))

vi.mock('@/services/upload-file', () => ({ uploadImage: mocks.uploadImage, uploadFile: vi.fn() }))

const deferred = () => {
  let reject!: (error: Error) => void
  const promise = new Promise<void>((_resolve, rejectPromise) => {
    reject = rejectPromise
  })
  return { promise, reject }
}

const deferredUpload = () => {
  let resolve!: (response: { data: { image_url: string } }) => void
  const promise = new Promise<{ data: { image_url: string } }>(done => { resolve = done })
  return { promise, resolve }
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
        plugins: [createTestI18n(), createPinia()],
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

  it('does not save an older avatar upload after a newer upload starts', async () => {
    const older = deferredUpload()
    const newer = deferredUpload()
    mocks.uploadImage.mockReset().mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    mocks.updateAvatar.mockReset().mockResolvedValue({ message: 'updated' })
    mocks.getCurrentUser.mockResolvedValue({ data: { id: 'account', avatar: 'new-icon' } })
    const wrapper = shallowMount(SettingModal, {
      props: { visible: true, initialTab: 'profile' },
      global: { plugins: [createTestI18n(), createPinia()], stubs: { 'a-modal': { template: '<div><slot /></div>' } } },
    })
    const { handleAvatarCustomRequest } = (
      wrapper.vm.$ as unknown as {
        setupState: { handleAvatarCustomRequest: (option: any) => unknown }
      }
    ).setupState
    const oldOption = { fileItem: { file: new File(['old'], 'old.png') }, onSuccess: vi.fn(), onError: vi.fn() }
    const newOption = { fileItem: { file: new File(['new'], 'new.png') }, onSuccess: vi.fn(), onError: vi.fn() }

    handleAvatarCustomRequest(oldOption)
    handleAvatarCustomRequest(newOption)
    older.resolve({ data: { image_url: 'old-icon' } })
    await flushPromises()

    expect(mocks.updateAvatar).not.toHaveBeenCalled()
    newer.resolve({ data: { image_url: 'new-icon' } })
    await flushPromises()

    expect(mocks.updateAvatar).toHaveBeenCalledTimes(1)
    expect(mocks.updateAvatar).toHaveBeenCalledWith('new-icon')
    expect(oldOption.onSuccess).not.toHaveBeenCalled()
    expect(newOption.onSuccess).toHaveBeenCalledWith('new-icon')
    wrapper.unmount()
  })
})
