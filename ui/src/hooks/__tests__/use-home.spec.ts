import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useGetHomeIntent } from '@/hooks/use-home'
import * as homeService from '@/services/home'

vi.mock('@/services/home', () => ({
  getHomeIntent: vi.fn(),
}))

describe('useGetHomeIntent', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns intent data and resets loading on success', async () => {
    const payload = {
      intent: '创建天气应用',
      confidence: 0.92,
      suggested_actions: [{ label: '创建应用', action: 'create_app', icon: 'plus' }],
      is_default: false,
    }
    vi.mocked(homeService.getHomeIntent).mockResolvedValue({ data: payload } as never)

    const { loading, loadHomeIntent } = useGetHomeIntent()

    expect(loading.value).toBe(false)
    const result = await loadHomeIntent()

    expect(result).toEqual(payload)
    expect(homeService.getHomeIntent).toHaveBeenCalledTimes(1)
    expect(loading.value).toBe(false)
  })

  it('resets loading when request fails', async () => {
    vi.mocked(homeService.getHomeIntent).mockRejectedValue(new Error('network error'))

    const { loading, loadHomeIntent } = useGetHomeIntent()

    await expect(loadHomeIntent()).rejects.toThrow('network error')
    expect(loading.value).toBe(false)
  })

  it('maintains loading state while a newer intent request is still pending', async () => {
    let resolveFirst: (v: any) => void = () => {}
    let resolveSecond: (v: any) => void = () => {}

    vi.mocked(homeService.getHomeIntent)
      .mockImplementationOnce(() => new Promise((res) => { resolveFirst = res }))
      .mockImplementationOnce(() => new Promise((res) => { resolveSecond = res }))

    const { loading, loadHomeIntent } = useGetHomeIntent()

    const call1 = loadHomeIntent()
    const call2 = loadHomeIntent()

    expect(loading.value).toBe(true)

    resolveFirst({ data: { intent: 'first', confidence: 0.5, suggested_actions: [], is_default: false } })
    await Promise.resolve()

    expect(loading.value).toBe(true)

    resolveSecond({ data: { intent: 'second', confidence: 0.9, suggested_actions: [], is_default: false } })
    await Promise.all([call1, call2])

    expect(loading.value).toBe(false)
  })
})
