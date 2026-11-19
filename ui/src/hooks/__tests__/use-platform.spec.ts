import { describe, expect, it, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({
  getWechatConfig: vi.fn(),
  updateWechatConfig: vi.fn(),
}))
vi.mock('@/services/platform', () => ({
  getWechatConfig: mocks.getWechatConfig,
  updateWechatConfig: mocks.updateWechatConfig,
}))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn() } }))

import { useGetWechatConfig, useUpdateWechatConfig } from '@/hooks/use-platform'
import { Message } from '@arco-design/web-vue'

const deferred = () => {
  let resolve!: (value: any) => void
  const promise = new Promise<any>((done) => { resolve = done })
  return { promise, resolve }
}

describe('use-platform', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

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

  describe('useUpdateWechatConfig', () => {
    it('ignores stale update completion and returns false when newer update was triggered', async () => {
      const p1 = deferred()
      const p2 = deferred()
      mocks.updateWechatConfig.mockReset().mockReturnValueOnce(p1.promise).mockReturnValueOnce(p2.promise)

      const { loading, handleUpdateWechatConfig } = useUpdateWechatConfig()

      const req1 = handleUpdateWechatConfig('app-1', { wechat_app_id: 'id-1', wechat_app_secret: 'sec-1', wechat_token: 'tok-1' })
      const req2 = handleUpdateWechatConfig('app-1', { wechat_app_id: 'id-2', wechat_app_secret: 'sec-2', wechat_token: 'tok-2' })

      expect(loading.value).toBe(true)

      p2.resolve({ message: 'Update 2 success' })
      const res2 = await req2
      expect(res2).toBe(true)
      expect(Message.success).toHaveBeenCalledWith('Update 2 success')

      p1.resolve({ message: 'Update 1 success' })
      const res1 = await req1
      expect(res1).toBe(false)
      expect(Message.success).toHaveBeenCalledTimes(1)
      expect(loading.value).toBe(false)
    })
  })
})
