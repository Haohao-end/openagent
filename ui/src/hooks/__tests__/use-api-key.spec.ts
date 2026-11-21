import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Message, Modal } from '@arco-design/web-vue'

const mocks = vi.hoisted(() => ({
  createApiKey: vi.fn(),
  updateApiKey: vi.fn(),
  updateApiKeyIsActive: vi.fn(),
  deleteApiKey: vi.fn(),
  getApiKeysWithPage: vi.fn(),
  routeQuery: { current_page: '2', page_size: '20' },
  credentialStore: { credential: { access_token: 'token-a', expire_at: 4102444800 } },
}))

vi.mock('@/services/api-key', () => ({
  createApiKey: mocks.createApiKey,
  deleteApiKey: mocks.deleteApiKey,
  getApiKeysWithPage: mocks.getApiKeysWithPage,
  updateApiKey: mocks.updateApiKey,
  updateApiKeyIsActive: mocks.updateApiKeyIsActive,
}))
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return { ...actual, useRoute: () => ({ query: mocks.routeQuery }) }
})
vi.mock('@arco-design/web-vue', () => ({
  Message: { success: vi.fn(), error: vi.fn() },
  Modal: { warning: vi.fn() },
}))
vi.mock('@/stores/credential', () => ({ useCredentialStore: () => mocks.credentialStore }))

import {
  useCreateApiKey,
  useDeleteApiKey,
  useGetApiKeysWithPage,
  useUpdateApiKey,
  useUpdateApiKeyIsActive,
} from '@/hooks/use-api-key'

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
    expect(Message.error).toHaveBeenCalledWith('delete failed')
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

  it('allows route pagination to supersede in-flight load and drops stale results', async () => {
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
    const page2Deferred = deferred<PageResult>()
    mocks.getApiKeysWithPage
      .mockReturnValueOnce(initialDeferred.promise)
      .mockReturnValueOnce(page2Deferred.promise)

    const { api_keys, paginator, loading, loadApiKeys } = useGetApiKeysWithPage()
    mocks.routeQuery.current_page = '1'

    const initialReq = loadApiKeys(true)
    expect(loading.value).toBe(true)

    // Duplicate call for the same page while loading is ignored
    await loadApiKeys(false)
    expect(mocks.getApiKeysWithPage).toHaveBeenCalledTimes(1)
    expect(loading.value).toBe(true)

    // Route target page changes to page 2: supersedes in-flight page 1 request
    mocks.routeQuery.current_page = '2'
    const page2Req = loadApiKeys(false)
    expect(mocks.getApiKeysWithPage).toHaveBeenCalledTimes(2)

    // Old page 1 resolves, but is dropped
    initialDeferred.resolve({
      data: { list: [{ id: 'key-1' }], paginator: { current_page: 1, page_size: 20, total_page: 2, total_record: 25 } },
    })
    await initialReq
    expect(api_keys.value).toEqual([])
    expect(loading.value).toBe(true)

    // Page 2 resolves and applies
    page2Deferred.resolve({
      data: { list: [{ id: 'key-2' }], paginator: { current_page: 2, page_size: 20, total_page: 2, total_record: 25 } },
    })
    await page2Req
    expect(api_keys.value).toEqual([{ id: 'key-2' }])
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

    await loadApiKeys(true)
    expect(api_keys.value).toEqual([])
    expect(paginator.value.total_page).toBe(0)
    expect(loading.value).toBe(false)

    await loadApiKeys()
    expect(mocks.getApiKeysWithPage).toHaveBeenCalledTimes(2)
    expect(api_keys.value).toEqual([{ id: 'new-key-1' }])
    expect(paginator.value.total_page).toBe(1)
    expect(loading.value).toBe(false)
  })
})

describe('useUpdateApiKeyIsActive race condition', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores stale response when a newer request completes first', async () => {
    let resolve1!: (val: any) => void
    let resolve2!: (val: any) => void
    const p1 = new Promise((r) => { resolve1 = r })
    const p2 = new Promise((r) => { resolve2 = r })

    mocks.updateApiKeyIsActive.mockReturnValueOnce(p1).mockReturnValueOnce(p2)

    const callback1 = vi.fn()
    const callback2 = vi.fn()
    const { handleUpdateApiKeyIsActive, loading } = useUpdateApiKeyIsActive()

    const req1 = handleUpdateApiKeyIsActive('key-1', false, callback1)
    const req2 = handleUpdateApiKeyIsActive('key-1', true, callback2)
    expect(loading.value).toBe(true)

    resolve2({ message: 'updated 2' })
    await req2
    expect(callback2).toHaveBeenCalledOnce()
    expect(Message.success).toHaveBeenCalledWith('updated 2')
    expect(loading.value).toBe(false)

    resolve1({ message: 'updated 1' })
    await req1
    expect(callback1).not.toHaveBeenCalled()
    expect(Message.success).not.toHaveBeenCalledWith('updated 1')
  })
})

describe('useUpdateApiKey race condition', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores stale update response when a newer request was dispatched', async () => {
    let resolve1!: (val: any) => void
    let resolve2!: (val: any) => void
    const p1 = new Promise((r) => { resolve1 = r })
    const p2 = new Promise((r) => { resolve2 = r })

    mocks.updateApiKey.mockReturnValueOnce(p1).mockReturnValueOnce(p2)

    const { handleUpdateApiKey, loading } = useUpdateApiKey()

    const req1 = handleUpdateApiKey('key-1', { remark: 'old', is_active: true })
    const req2 = handleUpdateApiKey('key-1', { remark: 'new', is_active: true })
    expect(loading.value).toBe(true)

    resolve2({ message: 'saved new' })
    await req2
    expect(Message.success).toHaveBeenCalledWith('saved new')
    expect(loading.value).toBe(false)

    resolve1({ message: 'saved old' })
    await req1
    expect(Message.success).not.toHaveBeenCalledWith('saved old')
  })
})

describe('useCreateApiKey race condition', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores stale create response when a newer request was dispatched', async () => {
    let resolve1!: (val: any) => void
    let resolve2!: (val: any) => void
    const p1 = new Promise((r) => { resolve1 = r })
    const p2 = new Promise((r) => { resolve2 = r })

    mocks.createApiKey.mockReturnValueOnce(p1).mockReturnValueOnce(p2)

    const { handleCreateApiKey, loading } = useCreateApiKey()

    const req1 = handleCreateApiKey({ remark: 'first', is_active: true })
    const req2 = handleCreateApiKey({ remark: 'second', is_active: true })
    expect(loading.value).toBe(true)

    resolve2({ message: 'created second', data: { api_key: 'key-2' } })
    const res2 = await req2
    expect(res2).toBe('key-2')
    expect(Message.success).toHaveBeenCalledWith('created second')
    expect(loading.value).toBe(false)

    resolve1({ message: 'created first', data: { api_key: 'key-1' } })
    const res1 = await req1
    expect(res1).toBeUndefined()
    expect(Message.success).not.toHaveBeenCalledWith('created first')
  })
})
