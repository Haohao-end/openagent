import { expect, it, vi } from 'vitest'

const { ssePost } = vi.hoisted(() => ({ ssePost: vi.fn() }))
vi.mock('@/utils/request', () => ({ get: vi.fn(), post: vi.fn(), ssePost }))

import { webAppChat } from '@/services/web-app'

it('forwards the abort signal to Web App chat streams', () => {
  const signal = new AbortController().signal
  const request = { query: 'hello', conversation_id: '', image_urls: [], enable_deep_thinking: false }
  const onData = vi.fn()

  void webAppChat('token-1', request, onData, signal)

  expect(ssePost).toHaveBeenCalledWith('/web-apps/token-1/chat', { body: request, signal }, onData)
})
