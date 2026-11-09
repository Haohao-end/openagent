import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import PublishedView from '../PublishedView.vue'

const mocks = vi.hoisted(() => ({
  route: { params: { app_id: 'app-a' } },
  getWechatConfig: vi.fn(),
  loadPublishedConfig: vi.fn(),
  getAppTags: vi.fn(),
  shareAppToSquare: vi.fn(),
  unshareAppFromSquare: vi.fn(),
}))
const routeState = reactive(mocks.route)

vi.mock('vue-router', async () => {
  return { useRoute: () => routeState, useRouter: () => ({ resolve: () => ({ href: '/' }) }) }
})

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key, locale: { value: 'zh-CN' } }) }))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() } }))
vi.mock('@/services/platform', () => ({ getWechatConfig: mocks.getWechatConfig, updateWechatConfig: vi.fn() }))
vi.mock('@/services/public-app', () => ({
  getAppTags: mocks.getAppTags,
  shareAppToSquare: mocks.shareAppToSquare,
  unshareAppFromSquare: mocks.unshareAppFromSquare,
}))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  return {
    useGetPublishedConfig: () => ({ loading: ref(false), published_config: ref({}), loadPublishedConfig: mocks.loadPublishedConfig }),
    useRegenerateWebAppToken: () => ({ loading: ref(false), token: ref(''), handleRegenerateWebAppToken: vi.fn() }),
  }
})

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise })
  return { promise, resolve }
}

describe('PublishedView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.params.app_id = 'app-a'
    mocks.loadPublishedConfig.mockResolvedValue(undefined)
  })

  it('does not render the leak alert banner in the published configuration page', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'src/views/space/apps/PublishedView.vue'),
      'utf8',
    )

    expect(source).not.toContain("t('appStudio.published.leakAlert')")
    expect(source).not.toContain('<a-alert class="mb-5">')
  })

  it('does not open the WeChat editor with the previous app config after route reuse', async () => {
    const openingRequest = deferred<{ data: { wechat_app_id: string; wechat_app_secret: string; wechat_token: string } }>()
    const newAppRequest = deferred<{ data: { wechat_app_id: string; wechat_app_secret: string; wechat_token: string } }>()
    const appConfig = (appId: string) => ({ data: { wechat_app_id: appId, wechat_app_secret: `${appId}-secret`, wechat_token: `${appId}-token` } })
    mocks.getWechatConfig
      .mockResolvedValueOnce(appConfig('app-a'))
      .mockReturnValueOnce(openingRequest.promise)
      .mockReturnValueOnce(newAppRequest.promise)

    const wrapper = shallowMount(PublishedView)
    await flushPromises()
    const state = (wrapper.vm.$ as any).setupState
    const opening = state.handleShowWechatConfigModal()
    await flushPromises()

    routeState.params.app_id = 'app-b'
    await flushPromises()
    expect(mocks.getWechatConfig).toHaveBeenLastCalledWith('app-b')

    openingRequest.resolve(appConfig('app-a'))
    await opening

    expect(state.wechatConfigModalVisible).toBe(false)
    expect(state.wechatConfigForm.wechat_app_id).not.toBe('app-a')
    newAppRequest.resolve(appConfig('app-b'))
    await flushPromises()
    wrapper.unmount()
  })
})
