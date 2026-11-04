import { expect, it, vi } from 'vitest'
const { ssePost } = vi.hoisted(() => ({ ssePost: vi.fn() }))
vi.mock('@/utils/request', () => ({ get: vi.fn(), post: vi.fn(), ssePost }))
import { debugChat } from '@/services/app'
it('forwards the abort signal to the debug stream request', () => {
  const signal = new AbortController().signal
  const onData = vi.fn()
  void debugChat('app-1', 'hello', [], '', onData, false, signal)
  expect(ssePost).toHaveBeenCalledWith('/apps/app-1/conversations', {
    body: { query: 'hello', image_urls: [], conversation_id: '', enable_deep_thinking: false },
    signal,
  }, onData)
})
