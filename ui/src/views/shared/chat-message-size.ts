type ChatMessageSizeSource = {
  query?: string
  image_urls?: string[]
  answer?: string
  answer_parts?: unknown[]
  artifacts?: unknown[]
  agent_thoughts?: unknown[]
  callable_trace_events?: unknown[]
  suggested_questions?: string[]
}

export const CHAT_MESSAGE_MIN_ITEM_SIZE = 180

const toStableJson = (value: unknown) => {
  try {
    return JSON.stringify(value ?? null)
  } catch {
    return String(value ?? '')
  }
}

const callableTraceLayoutSignature = (events: unknown) => {
  if (!Array.isArray(events) || events.length === 0) return ''
  const layoutEvents = events.map((value) => {
    let event = value
    if (typeof event === 'string') {
      try {
        event = JSON.parse(event)
      } catch {
        return ['malformed', event.length]
      }
    }
    if (!event || typeof event !== 'object' || Array.isArray(event)) return null
    const fields = event as Record<string, unknown>
    return [
      fields.event_id,
      fields.run_id,
      fields.parent_run_id,
      fields.phase,
      fields.run_type,
      fields.name,
      fields.status,
      fields.latency_ms,
      'inputs' in fields,
      'outputs' in fields,
      'error' in fields && fields.error !== null && fields.error !== '',
    ]
  })
  const serialized = toStableJson(layoutEvents)
  let hash = 2166136261
  for (let index = 0; index < serialized.length; index += 1) {
    hash = Math.imul(hash ^ serialized.charCodeAt(index), 16777619)
  }
  return `${events.length}:${serialized.length}:${hash >>> 0}`
}

const normalizeImageUrls = (value: unknown) => {
  if (!Array.isArray(value))
    return ''

  return value
    .map((item) => String(item ?? '').trim())
    .filter(Boolean)
    .join('|')
}

/**
 * Build a stable signature for message layout-relevant fields.
 *
 * DynamicScrollerItem only recomputes sizes when its sizeDependencies change.
 * The signature includes the content that can change rendered height.
 */
export const buildChatMessageSizeDependencies = (
  message: ChatMessageSizeSource,
  loading: boolean = false,
) => {
  return [
    String(message.query ?? ''),
    normalizeImageUrls(message.image_urls),
    String(message.answer ?? ''),
    toStableJson(message.answer_parts ?? []),
    toStableJson(message.artifacts ?? []),
    toStableJson(message.agent_thoughts ?? []),
    callableTraceLayoutSignature(message.callable_trace_events),
    toStableJson(message.suggested_questions ?? []),
    loading ? 1 : 0,
  ]
}
