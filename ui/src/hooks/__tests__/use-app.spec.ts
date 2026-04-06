import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useGetVersions } from '@/hooks/use-app'
import * as appService from '@/services/app'

vi.mock('@/services/app', async () => {
  const actual = await vi.importActual<typeof import('@/services/app')>('@/services/app')
  return {
    ...actual,
    getVersions: vi.fn(),
  }
})

describe('useGetVersions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads version list and resets loading on success', async () => {
    const payload = [
      {
        id: 'draft-version-id',
        app_id: 'app-1',
        version: 0,
        config_type: 'draft',
        config: { model_config: { provider: 'deepseek', model: 'deepseek-chat' } },
        is_current_published: false,
        label: '草稿',
        summary: '当前草稿版本',
        created_at: 1710000000,
        updated_at: 1710000100,
      },
      {
        id: 'published-version-id',
        app_id: 'app-1',
        version: 3,
        config_type: 'published',
        config: { model_config: { provider: 'deepseek', model: 'deepseek-chat' } },
        is_current_published: true,
        label: '版本 #003',
        summary: '当前线上版本',
        created_at: 1700000000,
        updated_at: 1700000100,
      },
    ]
    vi.mocked(appService.getVersions).mockResolvedValue({ data: { list: payload } } as never)

    const { loading, versions, loadVersions } = useGetVersions()

    expect(loading.value).toBe(false)
    await loadVersions('app-1')

    expect(appService.getVersions).toHaveBeenCalledWith('app-1')
    expect(versions.value).toEqual(payload)
    expect(loading.value).toBe(false)
  })

  it('resets loading when request fails', async () => {
    vi.mocked(appService.getVersions).mockRejectedValue(new Error('network error'))

    const { loading, loadVersions } = useGetVersions()

    await expect(loadVersions('app-1')).rejects.toThrow('network error')
    expect(loading.value).toBe(false)
  })
})
