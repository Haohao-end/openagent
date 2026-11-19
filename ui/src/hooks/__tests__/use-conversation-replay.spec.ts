import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useReplayMessage } from '../use-conversation'
import * as conversationService from '@/services/conversation'

describe('useReplayMessage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('executes replay and stores snapshot', async () => {
    const mockSnapshot = {
      message_id: 'msg-1',
      conversation_id: 'conv-1',
      app_id: 'app-1',
      input_snapshot: { query: 'test query', image_urls: [] },
      config_snapshot: {},
      patched_config: { preset_prompt: 'new prompt' },
      applied_patch_keys: ['preset_prompt'],
    }

    vi.spyOn(conversationService, 'replayMessage').mockResolvedValueOnce({
      code: 'success',
      data: mockSnapshot,
      message: '',
    })

    const { loading, snapshot, executeReplay } = useReplayMessage()
    expect(loading.value).toBe(false)
    expect(snapshot.value).toBeNull()

    const promise = executeReplay('msg-1', { patch: { preset_prompt: 'new prompt' } })
    expect(loading.value).toBe(true)

    const res = await promise
    expect(loading.value).toBe(false)
    expect(res).toEqual(mockSnapshot)
    expect(snapshot.value).toEqual(mockSnapshot)
  })

  it('ignores stale responses when newer request finishes first', async () => {
    let resolveFirst!: (value: any) => void
    let resolveSecond!: (value: any) => void

    const p1 = new Promise((resolve) => { resolveFirst = resolve })
    const p2 = new Promise((resolve) => { resolveSecond = resolve })

    vi.spyOn(conversationService, 'replayMessage')
      .mockReturnValueOnce(p1 as any)
      .mockReturnValueOnce(p2 as any)

    const { snapshot, executeReplay } = useReplayMessage()

    const req1 = executeReplay('msg-1', { patch: { preset_prompt: 'prompt 1' } })
    const req2 = executeReplay('msg-2', { patch: { preset_prompt: 'prompt 2' } })

    resolveSecond({ code: 'success', data: { message_id: 'msg-2', applied_patch_keys: [] } })
    await req2
    expect(snapshot.value?.message_id).toBe('msg-2')

    resolveFirst({ code: 'success', data: { message_id: 'msg-1', applied_patch_keys: [] } })
    await req1
    expect(snapshot.value?.message_id).toBe('msg-2')
  })

  it('resets state on clearReplay', () => {
    const { loading, snapshot, clearReplay } = useReplayMessage()
    snapshot.value = { message_id: 'msg-1' } as any
    loading.value = true

    clearReplay()
    expect(loading.value).toBe(false)
    expect(snapshot.value).toBeNull()
  })
})
