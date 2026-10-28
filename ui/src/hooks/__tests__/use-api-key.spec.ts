import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ updateApiKeyIsActive: vi.fn() }))

vi.mock('@/services/api-key', () => ({
  createApiKey: vi.fn(),
  deleteApiKey: vi.fn(),
  getApiKeysWithPage: vi.fn(),
  updateApiKey: vi.fn(),
  updateApiKeyIsActive: mocks.updateApiKeyIsActive,
}))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn() }, Modal: { warning: vi.fn() } }))

import { useUpdateApiKeyIsActive } from '@/hooks/use-api-key'

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
