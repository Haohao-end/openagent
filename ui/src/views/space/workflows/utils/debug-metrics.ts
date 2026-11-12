export type DebugNodeResult = {
  node_data: {
    id?: string
    node_type?: string
    type?: string
    title?: string
  }
  status?: string
  error?: string
  outputs: unknown
  latency: number
}

const MAX_DEBUG_NODE_OUTPUT_LENGTH = 4000
const MAX_DEBUG_NODE_OUTPUT_STRING_LENGTH = 1000
const MAX_DEBUG_NODE_OUTPUT_COLLECTION_ITEMS = 100
const MAX_DEBUG_NODE_OUTPUT_DEPTH = 8
const MAX_DEBUG_NODE_OUTPUT_TOTAL_ITEMS = 500

type DebugNodeOutputBudget = { remaining: number; truncated: boolean }

const normalizeDebugNodeOutput = (
  value: unknown,
  seen: WeakSet<object>,
  budget: DebugNodeOutputBudget,
  depth = 0,
): unknown => {
  if (typeof value === 'string') {
    if (value.length > MAX_DEBUG_NODE_OUTPUT_STRING_LENGTH) {
      budget.truncated = true
      return value.slice(0, MAX_DEBUG_NODE_OUTPUT_STRING_LENGTH)
    }
    return value
  }
  if (typeof value === 'bigint') return `${value}n`
  if (typeof value === 'function' || typeof value === 'symbol') return '[Unsupported value]'
  if (value === null || typeof value !== 'object') return value
  if (depth >= MAX_DEBUG_NODE_OUTPUT_DEPTH) {
    budget.truncated = true
    return '[Maximum depth reached]'
  }
  if (seen.has(value)) return '[Circular]'

  seen.add(value)
  try {
    if (Array.isArray(value)) {
      const count = Math.min(
        value.length,
        MAX_DEBUG_NODE_OUTPUT_COLLECTION_ITEMS,
        budget.remaining,
      )
      const normalized: unknown[] = []
      for (let index = 0; index < count; index += 1) {
        budget.remaining -= 1
        normalized.push(normalizeDebugNodeOutput(value[index], seen, budget, depth + 1))
      }
      if (value.length > count) budget.truncated = true
      return normalized
    }

    const normalized: Record<string, unknown> = Object.create(null)
    let count = 0
    for (const key in value) {
      if (!Object.prototype.hasOwnProperty.call(value, key)) continue
      if (count >= MAX_DEBUG_NODE_OUTPUT_COLLECTION_ITEMS || budget.remaining <= 0) {
        budget.truncated = true
        break
      }
      count += 1
      budget.remaining -= 1
      try {
        normalized[key] = normalizeDebugNodeOutput(
          (value as Record<string, unknown>)[key],
          seen,
          budget,
          depth + 1,
        )
      } catch {
        budget.truncated = true
        normalized[key] = '[Unserializable value]'
      }
    }
    return normalized
  } finally {
    seen.delete(value)
  }
}

const boundDebugNodeOutput = (value: string): string => {
  return value.length > MAX_DEBUG_NODE_OUTPUT_LENGTH
    ? `${value.slice(0, MAX_DEBUG_NODE_OUTPUT_LENGTH)}\n[truncated]`
    : value
}

export const formatDebugNodeOutputs = (outputs: unknown): string => {
  if (outputs === undefined) return '—'
  if (typeof outputs === 'string') return boundDebugNodeOutput(outputs)

  const budget = { remaining: MAX_DEBUG_NODE_OUTPUT_TOTAL_ITEMS, truncated: false }
  try {
    const normalized = outputs !== null && typeof outputs === 'object'
      ? normalizeDebugNodeOutput(outputs, new WeakSet<object>(), budget)
      : outputs
    const formatted = JSON.stringify(normalized, null, 2) ?? String(outputs)
    return boundDebugNodeOutput(`${formatted}${budget.truncated ? '\n[truncated]' : ''}`)
  } catch {
    return boundDebugNodeOutput(String(outputs))
  }
}

export const findWorkflowOutputs = (nodeResults: DebugNodeResult[]): unknown => {
  const endNodeResult = [...nodeResults].reverse().find((item) => (item.node_data?.node_type ?? item.node_data?.type) === 'end')
  return endNodeResult ? endNodeResult.outputs : null
}

const safeLatency = (value: number): number => Number.isFinite(value) && value >= 0 ? value : 0

export const sumWorkflowLatency = (nodeResults: DebugNodeResult[]): number => {
  return nodeResults.reduce((total, item) => total + safeLatency(item.latency), 0)
}

export const sumWorkflowToolLatency = (nodeResults: DebugNodeResult[]): number => {
  return nodeResults.reduce((total, item) => {
    if ((item.node_data?.node_type ?? item.node_data?.type) === 'tool') {
      return total + safeLatency(item.latency)
    }
    return total
  }, 0)
}
