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
  updateName: vi.fn(),
  updatePassword: vi.fn(),
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
  updateName: mocks.updateName,
  updatePassword: mocks.updatePassword,
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

const deferredSave = () => {
  let resolve!: () => void
  const promise = new Promise<void>(done => { resolve = done })
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

  it('keeps the latest avatar when an earlier save finishes last', async () => {
    const olderUpload = deferredUpload()
    const newerUpload = deferredUpload()
    const olderSave = deferredSave()
    const newerSave = deferredSave()
    let persistedAvatar = ''
    mocks.uploadImage.mockReset().mockReturnValueOnce(olderUpload.promise).mockReturnValueOnce(newerUpload.promise)
    mocks.updateAvatar.mockReset().mockImplementation((avatar: string) => {
      const save = avatar === 'old-icon' ? olderSave : newerSave
      return save.promise.then(() => {
        persistedAvatar = avatar
        return { message: 'updated' }
      })
    })
    mocks.getCurrentUser.mockReset().mockImplementation(async () => ({ data: { id: 'account', avatar: persistedAvatar } }))
    const wrapper = shallowMount(SettingModal, {
      props: { visible: true, initialTab: 'profile' },
      global: { plugins: [createTestI18n(), createPinia()], stubs: { 'a-modal': { template: '<div><slot /></div>' } } },
    })
    const { handleAvatarCustomRequest } = (
      wrapper.vm.$ as unknown as { setupState: { handleAvatarCustomRequest: (option: any) => unknown } }
    ).setupState
    const upload = (name: string) => ({ fileItem: { file: new File([name], `${name}.png`) }, onSuccess: vi.fn(), onError: vi.fn() })
    const oldOption = upload('old')
    const newOption = upload('new')

    handleAvatarCustomRequest(oldOption)
    olderUpload.resolve({ data: { image_url: 'old-icon' } })
    await flushPromises()
    handleAvatarCustomRequest(newOption)
    newerUpload.resolve({ data: { image_url: 'new-icon' } })
    await flushPromises()

    newerSave.resolve()
    await flushPromises()
    olderSave.resolve()
    await flushPromises()

    expect(persistedAvatar).toBe('new-icon')
    wrapper.unmount()
  })

  it('blocks concurrent name saves while an update is in progress', async () => {
    let resolveSave!: (value: any) => void
    mocks.updateName.mockReturnValue(new Promise((resolve) => { resolveSave = resolve }))
    mocks.getCurrentUser.mockResolvedValue({ data: { id: 'account', name: 'New Name' } })

    const wrapper = shallowMount(SettingModal, {
      props: { visible: true, initialTab: 'profile' },
      global: { plugins: [createTestI18n(), createPinia()], stubs: { 'a-modal': { template: '<div><slot /></div>' } } },
    })
    const state = (wrapper.vm.$ as any).setupState
    state.accountForm.name = 'New Name'

    const firstSave = state.handleSaveName()
    expect(mocks.updateName).toHaveBeenCalledTimes(1)

    await state.handleSaveName()
    expect(mocks.updateName).toHaveBeenCalledTimes(1)

    resolveSave({ message: 'success' })
    await firstSave
    wrapper.unmount()
  })

  it('blocks concurrent password saves while an update is in progress', async () => {
    let resolveSave!: (value: any) => void
    mocks.updatePassword.mockReturnValue(new Promise((resolve) => { resolveSave = resolve }))
    mocks.getCurrentUser.mockResolvedValue({ data: { id: 'account', name: 'User' } })

    const wrapper = shallowMount(SettingModal, {
      props: { visible: true, initialTab: 'security' },
      global: { plugins: [createTestI18n(), createPinia()], stubs: { 'a-modal': { template: '<div><slot /></div>' } } },
    })
    const state = (wrapper.vm.$ as any).setupState
    state.securityForm.current_password = 'old'
    state.securityForm.new_password = 'ValidPassword123'
    state.securityForm.confirm_password = 'ValidPassword123'

    const firstSave = state.handleSavePassword()
    expect(mocks.updatePassword).toHaveBeenCalledTimes(1)

    await state.handleSavePassword()
    expect(mocks.updatePassword).toHaveBeenCalledTimes(1)

    resolveSave({ message: 'success' })
    await firstSave
    wrapper.unmount()
  })
})
