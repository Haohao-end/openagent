import { expect, it, vi } from 'vitest'
const { ssePost } = vi.hoisted(() => ({ ssePost: vi.fn() }))
vi.mock('@/utils/request', () => ({ get: vi.fn(), post: vi.fn(), ssePost }))
import { mcpSchemaAssistantChat } from '@/services/ai'

it('forwards the abort signal to MCP schema streaming', () => {
  const signal = new AbortController().signal
  const onData = vi.fn()
  void mcpSchemaAssistantChat('question', onData, signal)
  expect(ssePost).toHaveBeenCalledWith('/ai/mcp-schema-chat', { body: { question: 'question' }, signal }, onData)
})
