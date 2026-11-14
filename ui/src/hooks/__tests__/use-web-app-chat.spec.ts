import { beforeEach, expect, it, vi } from 'vitest'
import { useWebAppChat } from '@/hooks/use-web-app'
import { webAppChat } from '@/services/web-app'
import { Message } from '@arco-design/web-vue'

vi.mock('@/services/web-app', () => ({ webAppChat: vi.fn() }))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: vi.fn() } }))

beforeEach(() => {
  vi.clearAllMocks()
})

it('silently finishes a chat canceled by its caller', async () => {
  vi.mocked(webAppChat).mockRejectedValueOnce(new Error('request canceled'))
  const controller = new AbortController()
  const { handleWebAppChat } = useWebAppChat()
  const request = handleWebAppChat('token-1', {
    query: 'hello',
    conversation_id: '',
    image_urls: [],
    enable_deep_thinking: false,
  }, vi.fn(), controller.signal)

  controller.abort()
  await expect(request).resolves.toBeUndefined()
  expect(Message.error).not.toHaveBeenCalled()
})
