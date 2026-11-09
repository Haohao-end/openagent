import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGenerateIconPreview, useRegenerateIcon } from '@/hooks/use-app'

const mocks = vi.hoisted(() => ({ generateIconPreview: vi.fn(), regenerateIcon: vi.fn(), error: vi.fn() }))

vi.mock('@/services/app', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/app')>()
  return {
    ...actual,
    generateIconPreview: (...args: unknown[]) => mocks.generateIconPreview(...args),
    regenerateIcon: (...args: unknown[]) => mocks.regenerateIcon(...args),
  }
})
vi.mock('@arco-design/web-vue', () => ({
  Message: { error: mocks.error, success: vi.fn() },
  Modal: { warning: vi.fn() },
}))

describe('app icon request errors', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('suppresses icon notifications when a modal session is stale', async () => {
    mocks.generateIconPreview.mockRejectedValueOnce(new Error('generation failed'))
    mocks.regenerateIcon.mockRejectedValueOnce(new Error('regeneration failed'))
    const { handleGenerateIconPreview } = useGenerateIconPreview()
    const { handleRegenerateIcon } = useRegenerateIcon()

    await expect(handleGenerateIconPreview('app', '', () => false)).rejects.toThrow('generation failed')
    await expect(handleRegenerateIcon('app-1', () => false)).rejects.toThrow('regeneration failed')

    expect(mocks.error).not.toHaveBeenCalled()
  })
})
