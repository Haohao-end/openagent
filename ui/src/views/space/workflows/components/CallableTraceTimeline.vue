<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

type TracePhase = 'start' | 'end' | 'error'
type TraceRunType = 'chain' | 'llm' | 'tool'
type CallableTrace = {
  event_id?: string
  run_id: string
  parent_run_id?: string | null
  run_type: TraceRunType
  phase: TracePhase
  name: string
  status: string
  inputs?: unknown
  outputs?: unknown
  error?: unknown
  latency_ms?: number
}

const props = defineProps<{ events: unknown[] }>()
const { t } = useI18n()
const phaseRank: Record<TracePhase, number> = { start: 0, end: 1, error: 2 }

const parseEvent = (value: unknown): CallableTrace | undefined => {
  let payload = value
  if (typeof payload === 'string') {
    try {
      payload = JSON.parse(payload)
    } catch {
      return undefined
    }
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return undefined
  const data = payload as Record<string, unknown>
  if (data.schema_version !== 1 || typeof data.run_id !== 'string' || !data.run_id.trim())
    return undefined
  if (!['chain', 'llm', 'tool'].includes(String(data.run_type))) return undefined
  if (!['start', 'end', 'error'].includes(String(data.phase))) return undefined

  const phase = data.phase as TracePhase
  const runType = data.run_type as TraceRunType
  const event: CallableTrace = {
    run_id: data.run_id,
    run_type: runType,
    phase,
    name: typeof data.name === 'string' && data.name.trim() ? data.name : data.run_id,
    status:
      typeof data.status === 'string' && data.status.trim()
        ? data.status
        : phase === 'start'
          ? 'running'
          : phase === 'error'
            ? 'failed'
            : 'succeeded',
  }
  if (typeof data.event_id === 'string') event.event_id = data.event_id
  if (data.parent_run_id === null || typeof data.parent_run_id === 'string') {
    event.parent_run_id = data.parent_run_id
  }
  if ('inputs' in data) event.inputs = data.inputs
  if ('outputs' in data) event.outputs = data.outputs
  if ('error' in data) event.error = data.error
  if (
    typeof data.latency_ms === 'number' &&
    Number.isFinite(data.latency_ms) &&
    data.latency_ms >= 0
  ) {
    event.latency_ms = data.latency_ms
  }
  return event
}

const MAX_VALUE_LENGTH = 4000
const MAX_STRING_LENGTH = 1000
const MAX_COLLECTION_ITEMS = 100
const MAX_VALUE_DEPTH = 8
const MAX_TOTAL_ITEMS = 500

const normalizeValue = (
  value: unknown,
  seen: WeakSet<object>,
  budget: { remaining: number },
  depth = 0,
): unknown => {
  if (typeof value === 'string') {
    return value.length > MAX_STRING_LENGTH
      ? `${value.slice(0, MAX_STRING_LENGTH)} [truncated]`
      : value
  }
  if (typeof value === 'bigint') return `${value}n`
  if (typeof value === 'function' || typeof value === 'symbol') return '[Unsupported value]'
  if (value === null || typeof value !== 'object') return value
  if (depth >= MAX_VALUE_DEPTH) return '[Maximum depth reached]'
  if (seen.has(value)) return '[Circular]'
  seen.add(value)
  if (Array.isArray(value)) {
    const count = Math.min(value.length, MAX_COLLECTION_ITEMS, budget.remaining)
    const items = []
    for (let index = 0; index < count; index += 1) {
      budget.remaining -= 1
      items.push(normalizeValue(value[index], seen, budget, depth + 1))
    }
    if (value.length > count) items.push('[truncated]')
    return items
  }
  const result: Record<string, unknown> = {}
  let count = 0
  for (const key in value) {
    if (!Object.prototype.hasOwnProperty.call(value, key)) continue
    if (count >= MAX_COLLECTION_ITEMS || budget.remaining <= 0) {
      result._truncated = true
      break
    }
    count += 1
    budget.remaining -= 1
    try {
      result[key] = normalizeValue((value as Record<string, unknown>)[key], seen, budget, depth + 1)
    } catch {
      result[key] = '[Unserializable value]'
    }
  }
  return result
}

const calls = computed(() => {
  const byRunId = new Map<string, CallableTrace>()
  const seenEventIds = new Set<string>()
  for (const rawEvent of props.events) {
    const event = parseEvent(rawEvent)
    if (!event || (event.event_id && seenEventIds.has(event.event_id))) continue
    if (event.event_id) seenEventIds.add(event.event_id)
    const previous = byRunId.get(event.run_id)
    if (!previous) {
      byRunId.set(event.run_id, event)
      continue
    }
    const isOutOfOrder = phaseRank[event.phase] < phaseRank[previous.phase]
    byRunId.set(event.run_id, {
      ...previous,
      ...event,
      phase: isOutOfOrder ? previous.phase : event.phase,
      status: isOutOfOrder ? previous.status : event.status,
      ...(isOutOfOrder
        ? { outputs: previous.outputs, error: previous.error, latency_ms: previous.latency_ms }
        : {}),
    })
  }
  return [...byRunId.values()]
})

const callById = computed(() => new Map(calls.value.map((call) => [call.run_id, call])))
const depthOf = (call: CallableTrace) => {
  const seen = new Set([call.run_id])
  let parentId = call.parent_run_id
  let depth = 0
  while (parentId && !seen.has(parentId)) {
    seen.add(parentId)
    depth += 1
    parentId = callById.value.get(parentId)?.parent_run_id
  }
  return Math.min(depth, 8)
}
const formatValue = (value: unknown) => {
  const seen = new WeakSet<object>()
  try {
    const normalized = normalizeValue(value, seen, { remaining: MAX_TOTAL_ITEMS })
    const formatted =
      typeof normalized === 'string' ? normalized : JSON.stringify(normalized, null, 2)
    if (!formatted) return 'null'
    return formatted.length > MAX_VALUE_LENGTH
      ? `${formatted.slice(0, MAX_VALUE_LENGTH)}\n[truncated]`
      : formatted
  } catch {
    return '[Unserializable value]'
  }
}
const runTypeLabel = (type: TraceRunType) => t(`workflowEditor.callableTrace.types.${type}`)
const phaseLabel = (phase: TracePhase) => t(`workflowEditor.callableTrace.phases.${phase}`)
const statusLabel = (status: string) => {
  const key = status.toLowerCase()
  if (['running', 'started', 'pending'].includes(key))
    return t('workflowEditor.callableTrace.status.running')
  if (['succeeded', 'success', 'completed', 'complete'].includes(key)) {
    return t('workflowEditor.callableTrace.status.succeeded')
  }
  if (['failed', 'error'].includes(key)) return t('workflowEditor.callableTrace.status.failed')
  return status
}
</script>

<template>
  <section
    v-if="calls.length"
    class="mt-4 flex flex-col gap-2"
    data-testid="callable-trace-timeline"
  >
    <h3 class="text-sm font-semibold text-gray-700">
      {{ t('workflowEditor.callableTrace.title') }}
    </h3>
    <ol class="flex flex-col gap-2">
      <li
        v-for="call in calls"
        :key="call.run_id"
        class="rounded-lg border border-gray-200 p-3"
        :data-status="call.status"
        :data-parent-run-id="call.parent_run_id ?? undefined"
        data-testid="callable-trace-call"
        :style="{ marginInlineStart: `${depthOf(call) * 16}px` }"
      >
        <div class="flex flex-wrap items-center gap-2">
          <h4 class="text-xs font-semibold text-gray-700">{{ call.name }}</h4>
          <span class="rounded bg-gray-100 px-2 py-0.5 text-xs">{{
            runTypeLabel(call.run_type)
          }}</span>
          <span class="text-xs text-gray-500">{{ phaseLabel(call.phase) }}</span>
          <span class="text-xs text-gray-500">{{ statusLabel(call.status) }}</span>
          <span v-if="call.latency_ms !== undefined" class="text-xs text-gray-500">
            {{ call.latency_ms }} ms
          </span>
        </div>
        <p
          v-if="call.parent_run_id && !callById.has(call.parent_run_id)"
          class="mt-1 text-xs text-gray-500"
        >
          {{ t('workflowEditor.callableTrace.parent', { id: call.parent_run_id }) }}
        </p>
        <details v-if="'inputs' in call" class="mt-2 text-xs">
          <summary class="cursor-pointer text-gray-600">
            {{ t('workflowEditor.callableTrace.inputs') }}
          </summary>
          <pre
            class="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words text-gray-600"
            data-testid="callable-trace-input"
            >{{ formatValue(call.inputs) }}</pre
          >
        </details>
        <details v-if="'outputs' in call" class="mt-2 text-xs">
          <summary class="cursor-pointer text-gray-600">
            {{ t('workflowEditor.callableTrace.outputs') }}
          </summary>
          <pre
            class="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words text-gray-600"
            data-testid="callable-trace-output"
            >{{ formatValue(call.outputs) }}</pre
          >
        </details>
        <details v-if="call.error !== undefined && call.error !== null" class="mt-2 text-xs">
          <summary class="cursor-pointer text-red-600">
            {{ t('workflowEditor.callableTrace.error') }}
          </summary>
          <pre
            class="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words text-red-700"
            data-testid="callable-trace-error"
            >{{ formatValue(call.error) }}</pre
          >
        </details>
        <p
          v-else-if="call.phase === 'error'"
          class="mt-2 text-xs text-red-700"
          data-testid="callable-trace-error"
        >
          {{ t('workflowEditor.callableTrace.errorMissing') }}
        </p>
      </li>
    </ol>
  </section>
</template>
