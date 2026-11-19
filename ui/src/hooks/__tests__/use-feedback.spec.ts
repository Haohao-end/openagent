import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useFeedback } from '../use-feedback'
import * as feedbackService from '@/services/feedback'

describe('useFeedback', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('submits feedback successfully and stores feedback id', async () => {
    vi.spyOn(feedbackService, 'createFeedback').mockResolvedValueOnce({
      code: 'success',
      data: { id: 'fb-123' },
      message: '',
    })

    const { loading, submittedFeedbackId, submitFeedback } = useFeedback()
    expect(loading.value).toBe(false)
    expect(submittedFeedbackId.value).toBeNull()

    const promise = submitFeedback('app-1', {
      target_id: 'msg-1',
      target_type: 'message',
      rating: 1,
      content: 'Great response!',
    })
    expect(loading.value).toBe(true)

    const res = await promise
    expect(loading.value).toBe(false)
    expect(res).toEqual({ id: 'fb-123' })
    expect(submittedFeedbackId.value).toBe('fb-123')
  })

  it('ignores stale submissions when multiple requests are fired', async () => {
    let resolveFirst!: (value: any) => void
    let resolveSecond!: (value: any) => void

    const p1 = new Promise((resolve) => { resolveFirst = resolve })
    const p2 = new Promise((resolve) => { resolveSecond = resolve })

    vi.spyOn(feedbackService, 'createFeedback')
      .mockReturnValueOnce(p1 as any)
      .mockReturnValueOnce(p2 as any)

    const { submittedFeedbackId, submitFeedback } = useFeedback()

    const req1 = submitFeedback('app-1', { target_id: 'msg-1', target_type: 'message', rating: 1 })
    const req2 = submitFeedback('app-1', { target_id: 'msg-2', target_type: 'message', rating: -1 })

    resolveSecond({ code: 'success', data: { id: 'fb-second' } })
    await req2
    expect(submittedFeedbackId.value).toBe('fb-second')

    resolveFirst({ code: 'success', data: { id: 'fb-first' } })
    await req1
    expect(submittedFeedbackId.value).toBe('fb-second')
  })

  it('clears state on clearFeedback', () => {
    const { loading, submittedFeedbackId, clearFeedback } = useFeedback()
    submittedFeedbackId.value = 'fb-123'
    loading.value = true

    clearFeedback()
    expect(loading.value).toBe(false)
    expect(submittedFeedbackId.value).toBeNull()
  })
})
