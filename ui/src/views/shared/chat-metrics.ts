export type MessageMetrics = {
  latency?: unknown
  total_token_count?: unknown
  answer?: unknown
  query?: unknown
  agent_thoughts?: Array<{ latency?: unknown }>
}

export const toPositiveNumber = (value: unknown): number => {
  const normalized = Number(value)
  return Number.isFinite(normalized) && normalized > 0 ? normalized : 0
}

export const toNonNegativeNumber = (value: unknown): number => {
  const normalized = Number(value)
  return Number.isFinite(normalized) && normalized >= 0 ? normalized : 0
}

export const estimateTokenCount = (content: string): number => {
  const normalized = String(content || '').trim()
  if (!normalized) return 0

  const cjkCount = (normalized.match(/[\u4e00-\u9fff]/g) || []).length
  const nonCjkTokens = (
    normalized
      .replace(/[\u4e00-\u9fff]/g, ' ')
      .match(/[A-Za-z0-9_]+|[^\s]/g) || []
  ).length

  return cjkCount + nonCjkTokens
}

export const normalizeMessageMetrics = (
  message: MessageMetrics | undefined,
  requestDurationMs: number = 0,
) => {
  if (!message) return

  const latencyFromMessage = toPositiveNumber(message.latency)
  const latencyFromThoughts = Array.isArray(message.agent_thoughts)
    ? message.agent_thoughts.reduce((sum, item) => sum + toPositiveNumber(item?.latency), 0)
    : 0
  const latencyFromDuration = requestDurationMs > 0 ? requestDurationMs / 1000 : 0
  const normalizedLatency = latencyFromMessage || latencyFromThoughts || latencyFromDuration
  message.latency = Number(normalizedLatency.toFixed(2))

  const tokenFromMessage = Math.floor(toNonNegativeNumber(message.total_token_count))
  if (tokenFromMessage > 0) {
    message.total_token_count = tokenFromMessage
    return
  }

  const answer = String(message.answer || '').trim()
  if (!answer) {
    message.total_token_count = 0
    return
  }

  const estimatedTokenCount =
    estimateTokenCount(String(message.query || '')) + estimateTokenCount(answer)
  message.total_token_count = estimatedTokenCount
}
