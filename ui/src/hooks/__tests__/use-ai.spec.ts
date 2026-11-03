import { describe, expect, it, vi } from 'vitest'
import { useGenerateSuggestedQuestions } from '@/hooks/use-ai'
import { generateSuggestedQuestions } from '@/services/ai'

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
