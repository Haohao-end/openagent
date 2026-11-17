import { describe, expect, it, vi } from 'vitest'
import { useGenerateSuggestedQuestions, useOptimizePrompt } from '@/hooks/use-ai'
import { generateSuggestedQuestions, optimizePrompt } from '@/services/ai'

vi.mock('@/services/ai', () => ({ generateSuggestedQuestions: vi.fn(), optimizePrompt: vi.fn() }))
const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise })
  return { promise, resolve }
}

describe('useGenerateSuggestedQuestions', () => {
  it('keeps the newest response when requests resolve out of order', async () => {
    const old = deferred<{ data: string[] }>()
    const latest = deferred<{ data: string[] }>()
    vi.mocked(generateSuggestedQuestions).mockReturnValueOnce(old.promise as never).mockReturnValueOnce(latest.promise as never)
    const state = useGenerateSuggestedQuestions()
    const oldRequest = state.handleGenerateSuggestedQuestions('old')
    const latestRequest = state.handleGenerateSuggestedQuestions('latest')
    latest.resolve({ data: ['latest'] })
    await latestRequest
    old.resolve({ data: ['old'] })
    await oldRequest
    expect(state.suggested_questions.value).toEqual(['latest'])
  })

  it('does not restore suggestions after they are cleared', async () => {
    const old = deferred<{ data: string[] }>()
    vi.mocked(generateSuggestedQuestions).mockReturnValue(old.promise as never)
    const state = useGenerateSuggestedQuestions()
    const request = state.handleGenerateSuggestedQuestions('old')
    state.clearSuggestedQuestions()
    old.resolve({ data: ['old'] })
    await request
    expect(state.suggested_questions.value).toEqual([])
  })
})

describe('useOptimizePrompt', () => {
  it('ignores chunks from an older stream after a newer optimization starts', async () => {
    let onOldData!: (res: { data: { optimize_prompt: string } }) => void
    let onNewData!: (res: { data: { optimize_prompt: string } }) => void
    const oldDeferred = deferred<void>()
    const newDeferred = deferred<void>()

    vi.mocked(optimizePrompt)
      .mockImplementationOnce((_prompt, callback) => {
        onOldData = callback
        return oldDeferred.promise as never
      })
      .mockImplementationOnce((_prompt, callback) => {
        onNewData = callback
        return newDeferred.promise as never
      })

    const { loading, optimize_prompt, handleOptimizePrompt } = useOptimizePrompt()
    const oldRequest = handleOptimizePrompt('prompt 1')
    const newRequest = handleOptimizePrompt('prompt 2')

    onNewData({ data: { optimize_prompt: 'new-chunk' } })
    onOldData({ data: { optimize_prompt: 'old-chunk' } })

    oldDeferred.resolve()
    await oldRequest
    expect(loading.value).toBe(true)
    expect(optimize_prompt.value).toBe('new-chunk')

    newDeferred.resolve()
    await newRequest
    expect(loading.value).toBe(false)
  })

  it('does not append chunks after prompt optimization is cleared', async () => {
    let onData!: (res: { data: { optimize_prompt: string } }) => void
    const pending = deferred<void>()
    vi.mocked(optimizePrompt).mockImplementationOnce((_prompt, callback) => {
      onData = callback
      return pending.promise as never
    })

    const { loading, optimize_prompt, handleOptimizePrompt, clearOptimizePrompt } = useOptimizePrompt()
    const request = handleOptimizePrompt('prompt')
    clearOptimizePrompt()

    onData({ data: { optimize_prompt: 'late-chunk' } })
    pending.resolve()
    await request

    expect(optimize_prompt.value).toBe('')
    expect(loading.value).toBe(false)
  })
})
