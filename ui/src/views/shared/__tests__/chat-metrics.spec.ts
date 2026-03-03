import { describe, expect, it } from 'vitest'
import {
  estimateTokenCount,
  normalizeMessageMetrics,
  toNonNegativeNumber,
  toPositiveNumber,
  type MessageMetrics,
} from '@/views/shared/chat-metrics'

describe('chat-metrics', () => {
  it('normalizes positive and non-negative numbers', () => {
    expect(toPositiveNumber(1.5)).toBe(1.5)
    expect(toPositiveNumber(0)).toBe(0)
    expect(toPositiveNumber('x')).toBe(0)

    expect(toNonNegativeNumber(0)).toBe(0)
    expect(toNonNegativeNumber(-1)).toBe(0)
    expect(toNonNegativeNumber('2')).toBe(2)
  })

  it('uses thought latency and estimates token count when message token is missing', () => {
    const message: MessageMetrics = {
      query: 'hello',
      answer: '你好 world',
      latency: 0,
      total_token_count: 0,
      agent_thoughts: [{ latency: 0.3 }, { latency: 0.4 }],
    }

    normalizeMessageMetrics(message)

    expect(message.latency).toBeCloseTo(0.7)
    expect(message.total_token_count).toBe(
      estimateTokenCount('hello') + estimateTokenCount('你好 world'),
    )
  })

  it('falls back to request duration when no valid latency is provided', () => {
    const message: MessageMetrics = {
      query: 'q',
      answer: 'a',
      latency: 0,
      total_token_count: 10,
      agent_thoughts: [],
    }

    normalizeMessageMetrics(message, 2800)

    expect(message.latency).toBe(2.8)
    expect(message.total_token_count).toBe(10)
  })
})
