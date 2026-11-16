import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Message, Modal } from '@arco-design/web-vue'

const mocks = vi.hoisted(() => ({
  updateApiKeyIsActive: vi.fn(),
  deleteApiKey: vi.fn(),
  getApiKeysWithPage: vi.fn(),
  routeQuery: { current_page: '2', page_size: '20' },
  credentialStore: { credential: { access_token: 'token-a', expire_at: 4102444800 } },
}))

vi.mock('@/services/api-key', () => ({
  createApiKey: vi.fn(),
  deleteApiKey: mocks.deleteApiKey,
  getApiKeysWithPage: mocks.getApiKeysWithPage,
  updateApiKey: vi.fn(),
  updateApiKeyIsActive: mocks.updateApiKeyIsActive,
}))
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return { ...actual, useRoute: () => ({ query: mocks.routeQuery }) }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { success: vi.fn() }, Modal: { warning: vi.fn() } }))
vi.mock('@/stores/credential', () => ({ useCredentialStore: () => mocks.credentialStore }))

import { useDeleteApiKey, useGetApiKeysWithPage, useUpdateApiKeyIsActive } from '@/hooks/use-api-key'

describe('useDeleteApiKey', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls the delete callback only after the API key is deleted', async () => {
    mocks.deleteApiKey.mockResolvedValueOnce({ message: 'deleted' })
    const callback = vi.fn()
    const { handleDeleteApiKey } = useDeleteApiKey()

    handleDeleteApiKey('key-1', callback)
    const onOk = vi.mocked(Modal.warning).mock.calls[0][0].onOk as () => Promise<void>
    await onOk()

    expect(callback).toHaveBeenCalledOnce()
    expect(Message.success).toHaveBeenCalledWith('deleted')

    callback.mockClear()
    vi.mocked(Message.success).mockClear()
    const requestError = new Error('delete failed')
    mocks.deleteApiKey.mockRejectedValueOnce(requestError)

    await expect(onOk()).rejects.toBe(requestError)
    expect(callback).not.toHaveBeenCalled()
    expect(Message.success).not.toHaveBeenCalled()
  })
})

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
    mocks.routeQuery.current_page = '2'
    mocks.routeQuery.page_size = '20'
  })

  it('falls back when positive fractional query values would round to zero', async () => {
    mocks.routeQuery.current_page = '0.5'
    mocks.routeQuery.page_size = '0.5'
    mocks.getApiKeysWithPage.mockResolvedValueOnce({ data: { list: [], paginator: { current_page: 1, page_size: 20, total_page: 0, total_record: 0 } } })
    await useGetApiKeysWithPage().loadApiKeys(true)
    expect(mocks.getApiKeysWithPage).toHaveBeenCalledWith({ current_page: 1, page_size: 20 })
  })

  it('ignores an older page response after a newer page has loaded', async () => {
    type PageResult = {
      data: {
        list: Array<{ id: string }>
        paginator: { current_page: number; page_size: number; total_page: number; total_record: number }
      }
    }
    const deferred = <T,>() => {
      let resolve!: (value: T) => void
      const promise = new Promise<T>((resolvePromise) => {
        resolve = resolvePromise
      })
      return { promise, resolve }
    }
    const page2 = deferred<PageResult>()
    const page3 = deferred<PageResult>()
    mocks.getApiKeysWithPage.mockReturnValueOnce(page2.promise).mockReturnValueOnce(page3.promise)
    const { api_keys, paginator, loadApiKeys } = useGetApiKeysWithPage()

    const olderRequest = loadApiKeys(true)
    mocks.routeQuery.current_page = '3'
    const newerRequest = loadApiKeys(true)
    page3.resolve({
      data: { list: [{ id: 'page-3' }], paginator: { current_page: 3, page_size: 20, total_page: 3, total_record: 60 } },
    })
    await newerRequest
    page2.resolve({
      data: { list: [{ id: 'page-2' }], paginator: { current_page: 2, page_size: 20, total_page: 3, total_record: 60 } },
    })
    await olderRequest

    expect(api_keys.value).toEqual([{ id: 'page-3' }])
    expect(paginator.value.current_page).toBe(3)
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


  it('ignores a page response from a previous credential', async () => {
    mocks.getApiKeysWithPage.mockResolvedValueOnce({
      data: { list: [{ id: 'user-a-key' }], paginator: { current_page: 2, page_size: 20, total_page: 2, total_record: 21 } },
    })
    const { api_keys, loadApiKeys } = useGetApiKeysWithPage()
    const request = loadApiKeys(true)
    mocks.credentialStore.credential = { access_token: 'token-b', expire_at: 4102444800 }

    await request

    expect(api_keys.value).toEqual([])
  })

  it('does not invalidate in-flight initial load or prematurely clear loading when duplicate pagination is called', async () => {
    type PageResult = {
      data: {
        list: Array<{ id: string }>
        paginator: { current_page: number; page_size: number; total_page: number; total_record: number }
      }
    }
    const deferred = <T,>() => {
      let resolve!: (value: T) => void
      const promise = new Promise<T>((resolvePromise) => {
        resolve = resolvePromise
      })
      return { promise, resolve }
    }
    const initialDeferred = deferred<PageResult>()
    mocks.getApiKeysWithPage.mockReturnValueOnce(initialDeferred.promise)
    const { api_keys, loading, loadApiKeys } = useGetApiKeysWithPage()

    // 1. 发起初次加载
    const initialRequest = loadApiKeys(true)
    expect(loading.value).toBe(true)

    // 2. 初次请求未完成时，触发无效的重复分页调用（init = false）
    const duplicatePagination = loadApiKeys(false)
    await duplicatePagination

    // loading 依然保持为 true，未被提前置为 false
    expect(loading.value).toBe(true)
    expect(mocks.getApiKeysWithPage).toHaveBeenCalledTimes(1)

    // 3. 初次加载成功返回
    initialDeferred.resolve({
      data: {
        list: [{ id: 'key-1' }],
        paginator: { current_page: 1, page_size: 20, total_page: 2, total_record: 25 },
      },
    })
    await initialRequest

    // 数据正常写入，未被判定为过期
    expect(api_keys.value).toEqual([{ id: 'key-1' }])
    expect(loading.value).toBe(false)
  })

  it('does not increment generation or alter loading when pagination is called without more pages', async () => {
    const { paginator, loading, loadApiKeys } = useGetApiKeysWithPage()
    paginator.value = { current_page: 3, page_size: 20, total_page: 2, total_record: 25 }

    await loadApiKeys(false)

    expect(mocks.getApiKeysWithPage).not.toHaveBeenCalled()
    expect(loading.value).toBe(false)
  })

  it('isolates old and new requests across credential switch and ignores stale errors', async () => {
    type PageResult = {
      data: {
        list: Array<{ id: string }>
        paginator: { current_page: number; page_size: number; total_page: number; total_record: number }
      }
    }
    const deferred = <T,>() => {
      let resolve!: (value: T) => void
      let reject!: (error: Error) => void
      const promise = new Promise<T>((res, rej) => {
        resolve = res
        reject = rej
      })
      return { promise, resolve, reject }
    }

    const accountARequest = deferred<PageResult>()
    const accountBRequest = deferred<PageResult>()
    mocks.getApiKeysWithPage
      .mockReturnValueOnce(accountARequest.promise)
      .mockReturnValueOnce(accountBRequest.promise)

    const { api_keys, loading, loadApiKeys } = useGetApiKeysWithPage()

    // 账号 A 加载
    mocks.credentialStore.credential = { access_token: 'token-a', expire_at: 4102444800 }
    const reqA = loadApiKeys(true)

    // 切换至账号 B
    mocks.credentialStore.credential = { access_token: 'token-b', expire_at: 4102444800 }
    const reqB = loadApiKeys(true)

    // 账号 B 成功
    accountBRequest.resolve({
      data: {
        list: [{ id: 'account-b-key' }],
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
      },
    })
    await reqB

    // 账号 A 旧请求失败
    accountARequest.reject(new Error('account A network error'))
    await expect(reqA).resolves.toBeUndefined()

    expect(api_keys.value).toEqual([{ id: 'account-b-key' }])
    expect(loading.value).toBe(false)
  })

  it('allows newer pagination requests to supersede active ones when route page changes', async () => {
    type PageResult = {
      data: {
        list: Array<{ id: string }>
        paginator: { current_page: number; page_size: number; total_page: number; total_record: number }
      }
    }
    const deferred = <T,>() => {
      let resolve!: (value: T) => void
      const promise = new Promise<T>((res) => {
        resolve = res
      })
      return { promise, resolve }
    }

    const page2Deferred = deferred<PageResult>()
    const page3Deferred = deferred<PageResult>()
    mocks.getApiKeysWithPage
      .mockReturnValueOnce(page2Deferred.promise)
      .mockReturnValueOnce(page3Deferred.promise)

    const { api_keys, paginator, loading, loadApiKeys } = useGetApiKeysWithPage()
    paginator.value = { current_page: 1, page_size: 20, total_page: 3, total_record: 50 }

    // 路由变更至第 2 页，触发分页请求
    mocks.routeQuery.current_page = '2'
    const page2Request = loadApiKeys(false)
    expect(loading.value).toBe(true)

    // 用户快速跳转或浏览历史前进至第 3 页，触发新的分页请求
    mocks.routeQuery.current_page = '3'
    const page3Request = loadApiKeys(false)
    expect(loading.value).toBe(true)
    expect(mocks.getApiKeysWithPage).toHaveBeenCalledTimes(2)

    // 此时第 2 页旧请求先返回
    page2Deferred.resolve({
      data: {
        list: [{ id: 'key-page-2' }],
        paginator: { current_page: 2, page_size: 20, total_page: 3, total_record: 50 },
      },
    })
    await page2Request

    // 旧请求已被新请求取代，不提交数据
    expect(api_keys.value).toEqual([])
    expect(paginator.value.current_page).toBe(1)
    expect(loading.value).toBe(true)

    // 第 3 页新请求返回
    page3Deferred.resolve({
      data: {
        list: [{ id: 'key-page-3' }],
        paginator: { current_page: 3, page_size: 20, total_page: 3, total_record: 50 },
      },
    })
    await page3Request

    // 第 3 页数据与分页状态成功提交
    expect(api_keys.value).toEqual([{ id: 'key-page-3' }])
    expect(paginator.value.current_page).toBe(3)
    expect(loading.value).toBe(false)
  })

  it('allows route page changes during uninitialized in-flight initial load to supersede initial load', async () => {
    type PageResult = {
      data: {
        list: Array<{ id: string }>
        paginator: { current_page: number; page_size: number; total_page: number; total_record: number }
      }
    }
    const deferred = <T,>() => {
      let resolve!: (value: T) => void
      const promise = new Promise<T>((res) => {
        resolve = res
      })
      return { promise, resolve }
    }

    const initialDeferred = deferred<PageResult>()
    const routePage2Deferred = deferred<PageResult>()
    mocks.getApiKeysWithPage
      .mockReturnValueOnce(initialDeferred.promise)
      .mockReturnValueOnce(routePage2Deferred.promise)

    const { api_keys, paginator, loading, loadApiKeys } = useGetApiKeysWithPage()

    // 初始加载触发（paginator 尚处于默认未初始化状态 total_page: 0）
    mocks.routeQuery.current_page = '1'
    const initialRequest = loadApiKeys(true)
    expect(loading.value).toBe(true)

    // 用户在初次加载未完成时切换路由至第 2 页，触发 loadApiKeys(false)
    mocks.routeQuery.current_page = '2'
    const routePage2Request = loadApiKeys(false)
    expect(loading.value).toBe(true)
    expect(mocks.getApiKeysWithPage).toHaveBeenCalledTimes(2)

    // 初次加载慢速返回，但其已被第 2 页请求取代
    initialDeferred.resolve({
      data: {
        list: [{ id: 'key-page-1' }],
        paginator: { current_page: 1, page_size: 20, total_page: 2, total_record: 30 },
      },
    })
    await initialRequest

    // 第 1 页旧结果不覆盖页面
    expect(api_keys.value).toEqual([])
    expect(loading.value).toBe(true)

    // 第 2 页新结果返回
    routePage2Deferred.resolve({
      data: {
        list: [{ id: 'key-page-2' }],
        paginator: { current_page: 2, page_size: 20, total_page: 2, total_record: 30 },
      },
    })
    await routePage2Request

    // 第 2 页数据与分页状态提交
    expect(api_keys.value).toEqual([{ id: 'key-page-2' }])
    expect(paginator.value.current_page).toBe(2)
    expect(loading.value).toBe(false)
  })

  it('allows out-of-range route to reach the server and trigger the last-page fallback', async () => {
    mocks.getApiKeysWithPage
      .mockResolvedValueOnce({
        data: {
          list: [],
          paginator: { current_page: 5, page_size: 20, total_page: 2, total_record: 25 },
        },
      })
      .mockResolvedValueOnce({
        data: {
          list: [{ id: 'fallback-page-2' }],
          paginator: { current_page: 2, page_size: 20, total_page: 2, total_record: 25 },
        },
      })

    const { api_keys, paginator, loading, loadApiKeys } = useGetApiKeysWithPage()
    paginator.value = { current_page: 1, page_size: 20, total_page: 2, total_record: 25 }

    // 路由跳转至超出总页数的第 5 页（例如删除数据后通过浏览历史访问）
    mocks.routeQuery.current_page = '5'
    await loadApiKeys(false)

    expect(mocks.getApiKeysWithPage).toHaveBeenNthCalledWith(1, { current_page: 5, page_size: 20 })
    expect(mocks.getApiKeysWithPage).toHaveBeenNthCalledWith(2, { current_page: 2, page_size: 20 })
    expect(api_keys.value).toEqual([{ id: 'fallback-page-2' }])
    expect(paginator.value.current_page).toBe(2)
    expect(loading.value).toBe(false)
  })

  it('allows reload after an empty page load when a new API key is created', async () => {
    mocks.getApiKeysWithPage
      .mockResolvedValueOnce({
        data: {
          list: [],
          paginator: { current_page: 1, page_size: 20, total_page: 0, total_record: 0 },
        },
      })
      .mockResolvedValueOnce({
        data: {
          list: [{ id: 'new-key-1' }],
          paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        },
      })

    const { api_keys, paginator, loading, loadApiKeys } = useGetApiKeysWithPage()
    mocks.routeQuery.current_page = '1'

    // 初次加载空列表
    await loadApiKeys(true)
    expect(api_keys.value).toEqual([])
    expect(paginator.value.total_page).toBe(0)
    expect(loading.value).toBe(false)

    // 创建模态框提交后，执行刷新回调 loadApiKeys()
    await loadApiKeys()
    expect(mocks.getApiKeysWithPage).toHaveBeenCalledTimes(2)
    expect(api_keys.value).toEqual([{ id: 'new-key-1' }])
    expect(paginator.value.total_page).toBe(1)
    expect(loading.value).toBe(false)
  })
})
