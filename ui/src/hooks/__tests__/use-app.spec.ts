import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Message, Modal } from '@arco-design/web-vue'

import {
  useCancelPublish,
  useDeleteApp,
  useFallbackHistoryToDraft,
  useGetApp,
  useGetAppsWithPage,
  useGetDraftAppConfig,
  useGetPublishedConfig,
  useGetVersions,
  useShareAppToSquare,
  useUnshareAppFromSquare,
  useUpdateDraftAppConfig,
} from '@/hooks/use-app'
import * as appService from '@/services/app'

vi.mock('@/services/app', async () => {
  const actual = await vi.importActual<typeof import('@/services/app')>('@/services/app')
  return {
    ...actual,
    getApp: vi.fn(),
    getAppsWithPage: vi.fn(),
    cancelPublish: vi.fn(),
    deleteApp: vi.fn(),
    shareAppToSquare: vi.fn(),
    unshareAppFromSquare: vi.fn(),
    getDraftAppConfig: vi.fn(),
    updateDraftAppConfig: vi.fn(),
    getPublishedConfig: vi.fn(),
    getVersions: vi.fn(),
    fallbackHistoryToDraft: vi.fn(),
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

  it('keeps the latest app versions when requests resolve out of order', async () => {
    let resolveOlder!: (value: { data: { list: Array<{ id: string }> } }) => void
    let resolveNewer!: (value: { data: { list: Array<{ id: string }> } }) => void
    const older = new Promise<{ data: { list: Array<{ id: string }> } }>((resolve) => { resolveOlder = resolve })
    const newer = new Promise<{ data: { list: Array<{ id: string }> } }>((resolve) => { resolveNewer = resolve })
    vi.mocked(appService.getVersions).mockReturnValueOnce(older as never).mockReturnValueOnce(newer as never)
    const { versions, loadVersions } = useGetVersions()

    const oldRequest = loadVersions('app-old')
    const newRequest = loadVersions('app-new')
    resolveNewer({ data: { list: [{ id: 'new-version' }] } })
    await newRequest
    resolveOlder({ data: { list: [{ id: 'old-version' }] } })
    await oldRequest

    expect(versions.value.map((version) => version.id)).toEqual(['new-version'])
  })

  it('loads draft capabilities with the draft app config', async () => {
    vi.mocked(appService.getDraftAppConfig).mockResolvedValue({
      data: {
        dialog_round: 3,
        model_config: { provider: 'openai', model: 'gpt-4o-mini', parameters: {} },
        capabilities: {
          image_input: { enabled: true },
        },
        preset_prompt: 'prompt',
        long_term_memory: { enable: false },
        opening_statement: '',
        opening_questions: [],
        suggested_after_answer: { enable: false },
        review_config: { enable: false },
        datasets: [],
        retrieval_config: { retrieval_strategy: 'semantic', k: 10, score: 0.5 },
        tools: [],
        mcp_bindings: [],
        mcp_tool_snapshots: [],
        agent_bindings: [
          {
            app_id: 'agent-1',
            invoke_mode: 'a2a',
            name: '客服助手',
            icon: '',
            description: '示例 Agent',
            source_scope: 'public',
            is_public: true,
            status: 'published',
            tool_name: 'agent_app_demo',
          },
        ],
        workflows: [],
        speech_to_text: { enable: false },
        text_to_speech: { enable: false, voice: 'alex', auto_play: false },
      },
    } as never)

    const { draftAppConfigForm, loadDraftAppConfig } = useGetDraftAppConfig()

    await loadDraftAppConfig('app-1')

    expect(appService.getDraftAppConfig).toHaveBeenCalledWith('app-1')
    expect(draftAppConfigForm.value.capabilities).toEqual({
      image_input: { enabled: true },
    })
    expect(draftAppConfigForm.value.mcp_tool_snapshots).toEqual([])
    expect(draftAppConfigForm.value.agent_bindings).toEqual([
      {
        app_id: 'agent-1',
        invoke_mode: 'a2a',
        name: '客服助手',
        icon: '',
        description: '示例 Agent',
        source_scope: 'public',
        is_public: true,
        status: 'published',
        tool_name: 'agent_app_demo',
      },
    ])
  })

  it('resets loading when request fails', async () => {
    vi.mocked(appService.getVersions).mockRejectedValue(new Error('network error'))

    const { loading, loadVersions } = useGetVersions()

    await expect(loadVersions('app-1')).rejects.toThrow('network error')
    expect(loading.value).toBe(false)
  })
})

describe('useGetDraftAppConfig', () => {
  it('keeps the latest draft config when requests resolve out of order', async () => {
    const deferred = <T,>() => {
      let resolve!: (value: T) => void
      const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise })
      return { promise, resolve }
    }
    const older = deferred<{ data: { preset_prompt: string } }>()
    const newer = deferred<{ data: { preset_prompt: string } }>()
    vi.mocked(appService.getDraftAppConfig)
      .mockReturnValueOnce(older.promise as never)
      .mockReturnValueOnce(newer.promise as never)
    const { draftAppConfigForm, loadDraftAppConfig } = useGetDraftAppConfig()

    const olderRequest = loadDraftAppConfig('app-old')
    const newerRequest = loadDraftAppConfig('app-new')
    newer.resolve({ data: { preset_prompt: 'new prompt' } })
    await newerRequest
    older.resolve({ data: { preset_prompt: 'old prompt' } })
    await olderRequest

    expect(draftAppConfigForm.value.preset_prompt).toBe('new prompt')
  })
})

describe('useGetPublishedConfig', () => {
  it('ignores an older route response after the selected app changes', async () => {
    const deferred = <T,>() => {
      let resolve!: (value: T) => void
      const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise })
      return { promise, resolve }
    }
    const oldResponse = deferred<{ data: { app_id: string } }>()
    const currentResponse = deferred<{ data: { app_id: string } }>()
    vi.mocked(appService.getPublishedConfig)
      .mockReturnValueOnce(oldResponse.promise as never)
      .mockReturnValueOnce(currentResponse.promise as never)
    const { published_config, loadPublishedConfig } = useGetPublishedConfig()

    const oldRequest = loadPublishedConfig('app-old')
    const currentRequest = loadPublishedConfig('app-current')
    currentResponse.resolve({ data: { app_id: 'app-current' } })
    await currentRequest
    oldResponse.resolve({ data: { app_id: 'app-old' } })
    await oldRequest

    expect(published_config.value).toEqual({ app_id: 'app-current' })
  })
})

describe('useUpdateDraftAppConfig', () => {
  it('stays loading until every overlapping draft save finishes', async () => {
    const deferred = <T,>() => {
      let resolve!: (value: T) => void
      const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise })
      return { promise, resolve }
    }
    const first = deferred<{ message: string }>()
    const second = deferred<{ message: string }>()
    vi.mocked(appService.updateDraftAppConfig)
      .mockReturnValueOnce(first.promise as never)
      .mockReturnValueOnce(second.promise as never)
    const { loading, handleUpdateDraftAppConfig } = useUpdateDraftAppConfig()

    const firstSave = handleUpdateDraftAppConfig('app-1', { preset_prompt: 'first' } as never)
    const secondSave = handleUpdateDraftAppConfig('app-1', { opening_statement: 'second' } as never)
    first.resolve({ message: 'saved' })
    await firstSave

    expect(loading.value).toBe(true)
    second.resolve({ message: 'saved' })
    await secondSave
    expect(loading.value).toBe(false)
  })
})

describe('useFallbackHistoryToDraft', () => {
  it('runs the refresh callback only after a successful rollback', async () => {
    const callback = vi.fn()
    const { loading, handleFallbackHistoryToDraft } = useFallbackHistoryToDraft()
    vi.mocked(appService.fallbackHistoryToDraft).mockRejectedValueOnce(new Error('offline'))

    await expect(handleFallbackHistoryToDraft('app-1', 'version-1', callback)).rejects.toThrow('offline')
    expect(callback).not.toHaveBeenCalled()
    expect(loading.value).toBe(false)

    vi.mocked(appService.fallbackHistoryToDraft).mockResolvedValueOnce({ message: 'restored' } as never)
    await handleFallbackHistoryToDraft('app-1', 'version-1', callback)
    expect(callback).toHaveBeenCalledTimes(1)
  })
})

describe('useGetApp', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not let an older app response replace the latest app', async () => {
    const createDeferred = () => {
      let resolve!: (value: { data: { id: string; name: string } }) => void
      const promise = new Promise<{ data: { id: string; name: string } }>((resolvePromise) => {
        resolve = resolvePromise
      })
      return { promise, resolve }
    }
    const olderResponse = createDeferred()
    const newerResponse = createDeferred()
    vi.mocked(appService.getApp)
      .mockReturnValueOnce(olderResponse.promise as never)
      .mockReturnValueOnce(newerResponse.promise as never)

    const { app, loadApp } = useGetApp()
    const olderRequest = loadApp('app-old')
    const newerRequest = loadApp('app-new')

    newerResponse.resolve({ data: { id: 'app-new', name: 'New App' } })
    await newerRequest
    olderResponse.resolve({ data: { id: 'app-old', name: 'Old App' } })
    await olderRequest

    expect(app.value).toEqual({ id: 'app-new', name: 'New App' })
  })

  it('keeps loading while the latest app request is pending', async () => {
    const createDeferred = () => {
      let resolve!: (value: { data: { id: string } }) => void
      const promise = new Promise<{ data: { id: string } }>((resolvePromise) => {
        resolve = resolvePromise
      })
      return { promise, resolve }
    }
    const olderResponse = createDeferred()
    const newerResponse = createDeferred()
    vi.mocked(appService.getApp)
      .mockReturnValueOnce(olderResponse.promise as never)
      .mockReturnValueOnce(newerResponse.promise as never)

    const { loading, loadApp } = useGetApp()
    const olderRequest = loadApp('app-old')
    const newerRequest = loadApp('app-new')

    olderResponse.resolve({ data: { id: 'app-old' } })
    await olderRequest
    expect(loading.value).toBe(true)

    newerResponse.resolve({ data: { id: 'app-new' } })
    await newerRequest
    expect(loading.value).toBe(false)
  })

  it('ignores an older app error after a newer app request succeeds', async () => {
    const createDeferred = () => {
      let resolve!: (value: { data: { id: string; name: string } }) => void
      let reject!: (reason?: unknown) => void
      const promise = new Promise<{ data: { id: string; name: string } }>((resolvePromise, rejectPromise) => {
        resolve = resolvePromise
        reject = rejectPromise
      })
      return { promise, resolve, reject }
    }
    const olderResponse = createDeferred()
    const newerResponse = createDeferred()
    vi.mocked(appService.getApp)
      .mockReturnValueOnce(olderResponse.promise as never)
      .mockReturnValueOnce(newerResponse.promise as never)
    const { app, loading, loadApp } = useGetApp()

    const olderRequest = loadApp('app-old')
    const newerRequest = loadApp('app-new')
    newerResponse.resolve({ data: { id: 'app-new', name: 'New App' } })
    await newerRequest
    olderResponse.reject(new Error('stale app request failed'))

    await expect(olderRequest).resolves.toBeUndefined()
    expect(app.value).toEqual({ id: 'app-new', name: 'New App' })
    expect(loading.value).toBe(false)
  })

  it('reports an error from the latest app request and resets loading', async () => {
    const originalError = new Error('latest app request failed')
    vi.mocked(appService.getApp).mockRejectedValueOnce(originalError)
    const { loading, loadApp } = useGetApp()

    await expect(loadApp('app-current')).rejects.toBe(originalError)

    expect(loading.value).toBe(false)
  })
})

describe('useDeleteApp', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const openDeleteConfirmation = async () => {
    const warningSpy = vi.spyOn(Modal, 'warning').mockImplementation(() => undefined as never)
    const callback = vi.fn()
    const { handleDeleteApp } = useDeleteApp()

    await handleDeleteApp('app-1', callback)

    return { callback, onOk: warningSpy.mock.calls[0][0].onOk as () => Promise<void> }
  }

  it('calls the callback once after a successful delete', async () => {
    vi.mocked(appService.deleteApp).mockResolvedValueOnce({ message: 'Deleted' } as never)
    const successSpy = vi.spyOn(Message, 'success').mockImplementation(() => undefined as never)
    const { callback, onOk } = await openDeleteConfirmation()

    await onOk()

    expect(callback).toHaveBeenCalledTimes(1)
    expect(successSpy).toHaveBeenCalledWith('Deleted')
  })

  it('does not call the callback or show success when delete fails', async () => {
    const originalError = new Error('delete failed')
    vi.mocked(appService.deleteApp).mockRejectedValueOnce(originalError)
    const successSpy = vi.spyOn(Message, 'success').mockImplementation(() => undefined as never)
    const { callback, onOk } = await openDeleteConfirmation()

    await expect(onOk()).rejects.toBe(originalError)

    expect(callback).not.toHaveBeenCalled()
    expect(successSpy).not.toHaveBeenCalled()
  })
})

describe('useCancelPublish', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const openCancelConfirmation = async () => {
    const warningSpy = vi.spyOn(Modal, 'warning').mockImplementation(() => undefined as never)
    const callback = vi.fn()
    const { loading, handleCancelPublish } = useCancelPublish()

    await handleCancelPublish('app-1', callback)

    return { callback, loading, onOk: warningSpy.mock.calls[0][0].onOk as () => Promise<void> }
  }

  it('calls the callback after cancel-publish succeeds and resets loading', async () => {
    let resolveCancel!: () => void
    const pendingCancel = new Promise<void>((resolve) => { resolveCancel = resolve })
    vi.mocked(appService.cancelPublish).mockReturnValueOnce(pendingCancel as never)
    const successSpy = vi.spyOn(Message, 'success').mockImplementation(() => undefined as never)
    const { callback, loading, onOk } = await openCancelConfirmation()

    const cancelRequest = onOk()
    expect(loading.value).toBe(true)
    resolveCancel()
    await cancelRequest

    expect(callback).toHaveBeenCalledTimes(1)
    expect(successSpy).toHaveBeenCalledOnce()
    expect(loading.value).toBe(false)
  })

  it('does not call the callback when cancel-publish fails and resets loading', async () => {
    const originalError = new Error('cancel publish failed')
    vi.mocked(appService.cancelPublish).mockRejectedValueOnce(originalError)
    const successSpy = vi.spyOn(Message, 'success').mockImplementation(() => undefined as never)
    const { callback, loading, onOk } = await openCancelConfirmation()

    const cancelRequest = onOk()
    expect(loading.value).toBe(true)
    await expect(cancelRequest).rejects.toBe(originalError)

    expect(callback).not.toHaveBeenCalled()
    expect(successSpy).not.toHaveBeenCalled()
    expect(loading.value).toBe(false)
  })
})

describe('useShareAppToSquare', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('calls the callback after sharing succeeds', async () => {
    vi.mocked(appService.shareAppToSquare).mockResolvedValueOnce({ message: 'Shared' } as never)
    const callback = vi.fn()
    const { handleShareAppToSquare } = useShareAppToSquare()

    await handleShareAppToSquare('app-1', 'agents', callback)

    expect(callback).toHaveBeenCalledTimes(1)
  })

  it('does not call the callback when sharing fails', async () => {
    const originalError = new Error('share failed')
    vi.mocked(appService.shareAppToSquare).mockRejectedValueOnce(originalError)
    const callback = vi.fn()
    const { loading, handleShareAppToSquare } = useShareAppToSquare()

    await expect(handleShareAppToSquare('app-1', 'agents', callback)).rejects.toBe(originalError)

    expect(callback).not.toHaveBeenCalled()
    expect(loading.value).toBe(false)
  })
})

describe('useUnshareAppFromSquare', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const openUnshareConfirmation = async () => {
    const warningSpy = vi.spyOn(Modal, 'warning').mockImplementation(() => undefined as never)
    const callback = vi.fn()
    const { loading, handleUnshareAppFromSquare } = useUnshareAppFromSquare()

    await handleUnshareAppFromSquare('app-1', callback)

    return { callback, loading, onOk: warningSpy.mock.calls[0][0].onOk as () => Promise<void> }
  }

  it('calls the callback after unsharing succeeds and resets loading', async () => {
    vi.mocked(appService.unshareAppFromSquare).mockResolvedValueOnce({ message: 'Unshared' } as never)
    const successSpy = vi.spyOn(Message, 'success').mockImplementation(() => undefined as never)
    const { callback, loading, onOk } = await openUnshareConfirmation()

    const unshareRequest = onOk()
    expect(loading.value).toBe(true)
    await unshareRequest

    expect(callback).toHaveBeenCalledTimes(1)
    expect(successSpy).toHaveBeenCalledOnce()
    expect(loading.value).toBe(false)
  })

  it('does not call the callback when unsharing fails and resets loading', async () => {
    const originalError = new Error('unshare failed')
    vi.mocked(appService.unshareAppFromSquare).mockRejectedValueOnce(originalError)
    const successSpy = vi.spyOn(Message, 'success').mockImplementation(() => undefined as never)
    const { callback, loading, onOk } = await openUnshareConfirmation()

    const unshareRequest = onOk()
    expect(loading.value).toBe(true)
    await expect(unshareRequest).rejects.toBe(originalError)

    expect(callback).not.toHaveBeenCalled()
    expect(successSpy).not.toHaveBeenCalled()
    expect(loading.value).toBe(false)
  })
})

describe('useGetAppsWithPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores an older search response after a newer search completes', async () => {
    const deferred = <T,>() => {
      let resolve!: (value: T) => void
      const promise = new Promise<T>((resolvePromise) => (resolve = resolvePromise))
      return { promise, resolve }
    }
    const response = (id: string) => ({
      data: { list: [{ id }], paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 } },
    })
    const oldResponse = deferred<ReturnType<typeof response>>()
    const newResponse = deferred<ReturnType<typeof response>>()
    vi.mocked(appService.getAppsWithPage)
      .mockReturnValueOnce(oldResponse.promise as never)
      .mockReturnValueOnce(newResponse.promise as never)
    const { apps, loadApps } = useGetAppsWithPage()

    const oldRequest = loadApps(true, 'old')
    const newRequest = loadApps(true, 'new')
    newResponse.resolve(response('new'))
    await newRequest
    oldResponse.resolve(response('old'))
    await oldRequest

    expect(apps.value.map((app) => app.id)).toEqual(['new'])
  })

  it('ignores an older search error after a newer search completes', async () => {
    const deferred = <T,>() => {
      let resolve!: (value: T) => void
      let reject!: (reason?: unknown) => void
      const promise = new Promise<T>((resolvePromise, rejectPromise) => {
        resolve = resolvePromise
        reject = rejectPromise
      })
      return { promise, resolve, reject }
    }
    const response = (id: string) => ({
      data: { list: [{ id }], paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 } },
    })
    const olderResponse = deferred<ReturnType<typeof response>>()
    const newerResponse = deferred<ReturnType<typeof response>>()
    vi.mocked(appService.getAppsWithPage)
      .mockReturnValueOnce(olderResponse.promise as never)
      .mockReturnValueOnce(newerResponse.promise as never)
    const { apps, loading, loadApps } = useGetAppsWithPage()

    const olderRequest = loadApps(true, 'old')
    const newerRequest = loadApps(true, 'new')
    newerResponse.resolve(response('new'))
    await newerRequest
    olderResponse.reject(new Error('stale search failed'))

    await expect(olderRequest).resolves.toBeUndefined()
    expect(apps.value.map((app) => app.id)).toEqual(['new'])
    expect(loading.value).toBe(false)
  })

  it('reports an error from the latest search and resets loading', async () => {
    const originalError = new Error('latest search failed')
    vi.mocked(appService.getAppsWithPage).mockRejectedValueOnce(originalError)
    const { loading, loadApps } = useGetAppsWithPage()

    await expect(loadApps(true, 'latest')).rejects.toBe(originalError)

    expect(loading.value).toBe(false)
  })
})
