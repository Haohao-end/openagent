import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  useFallbackHistoryToDraft,
  useGetApp,
  useGetAppsWithPage,
  useGetDraftAppConfig,
  useGetVersions,
} from '@/hooks/use-app'
import * as appService from '@/services/app'

vi.mock('@/services/app', async () => {
  const actual = await vi.importActual<typeof import('@/services/app')>('@/services/app')
  return {
    ...actual,
    getApp: vi.fn(),
    getAppsWithPage: vi.fn(),
    getDraftAppConfig: vi.fn(),
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
})

describe('useGetAppsWithPage', () => {
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
})
