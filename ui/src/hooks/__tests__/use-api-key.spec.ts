import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  updateApiKeyIsActive: vi.fn(),
  getApiKeysWithPage: vi.fn(),
  routeQuery: { current_page: '2', page_size: '20' },
}))

vi.mock('@/services/api-key', () => ({
  createApiKey: vi.fn(),
  deleteApiKey: vi.fn(),
  getApiKeysWithPage: mocks.getApiKeysWithPage,
  updateApiKey: vi.fn(),
  updateApiKeyIsActive: mocks.updateApiKeyIsActive,
}))
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return { ...actual, useRoute: () => ({ query: mocks.routeQuery }) }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn() }, Modal: { warning: vi.fn() } }))

import { useGetApiKeysWithPage, useUpdateApiKeyIsActive } from '@/hooks/use-api-key'

describe('useUpdateApiKeyIsActive', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('updates the row only after the API request succeeds', async () => {
    const callback = vi.fn()
    const { loading, handleUpdateApiKeyIsActive } = useUpdateApiKeyIsActive()
    mocks.updateApiKeyIsActive.mockRejectedValueOnce(new Error('network error'))
    await expect(handleUpdateApiKeyIsActive('key-1', false, callback)).rejects.toThrow('network error')
    expect(callback).not.toHaveBeenCalled()
    expect(loading.value).toBe(false)

    mocks.updateApiKeyIsActive.mockResolvedValueOnce({ message: 'updated' })
    await handleUpdateApiKeyIsActive('key-1', false, callback)
    expect(callback).toHaveBeenCalledOnce()
  })
})


describe('useGetApiKeysWithPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads the last remaining page when the current page becomes empty', async () => {
    mocks.getApiKeysWithPage
      .mockResolvedValueOnce({ data: { list: [], paginator: { current_page: 2, page_size: 20, total_page: 1, total_record: 20 } } })
      .mockResolvedValueOnce({ data: { list: [{ id: 'key-1' }], paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 20 } } })
    const { api_keys, paginator, loadApiKeys } = useGetApiKeysWithPage()
    paginator.value = { current_page: 2, page_size: 20, total_page: 2, total_record: 21 }

    await loadApiKeys()

    expect(mocks.getApiKeysWithPage).toHaveBeenNthCalledWith(2, { current_page: 1, page_size: 20 })
    expect(api_keys.value).toEqual([{ id: 'key-1' }])
    expect(paginator.value.current_page).toBe(1)
  })
})
