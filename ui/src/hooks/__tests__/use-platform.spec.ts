import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ getWechatConfig: vi.fn() }))
vi.mock('@/services/platform', () => ({ getWechatConfig: mocks.getWechatConfig, updateWechatConfig: vi.fn() }))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn() } }))

import { useGetWechatConfig } from '@/hooks/use-platform'

const deferred = () => {
  let resolve!: (value: any) => void
  const promise = new Promise<any>((done) => { resolve = done })
  return { promise, resolve }
}

describe('useGetWechatConfig', () => {
  it('keeps the active app config when a previous route request resolves later', async () => {
    const oldApp = deferred()
    const currentApp = deferred()
    mocks.getWechatConfig.mockReset().mockReturnValueOnce(oldApp.promise).mockReturnValueOnce(currentApp.promise)
    const hook = useGetWechatConfig()

    const oldRequest = hook.loadWechatConfig('app-old')
    const currentRequest = hook.loadWechatConfig('app-current')
    currentApp.resolve({ data: { app_id: 'app-current' } })
    await currentRequest
    oldApp.resolve({ data: { app_id: 'app-old' } })
    await oldRequest

    expect(hook.wechat_config.value).toEqual({ app_id: 'app-current' })
  })
})
