import { QueueEvent } from '@/config'
import {
  buildChatOutputParts,
  extractInlineImageUrls,
  mergeChatArtifacts,
} from './chat-output'

export type CallableTraceEvent = {
  schema_version?: number
  event_id?: string
  run_id?: string
  parent_run_id?: string | null
  phase?: string
  run_type?: string
  name?: string
  status?: string
  inputs?: unknown
  outputs?: unknown
  error?: unknown
  latency_ms?: number | null
}

type StreamEventData = CallableTraceEvent & {
  id?: string
  message_id?: string
  task_id?: string
  conversation_id?: string
  event?: string
  thought?: string
  observation?: string
  tool?: string
  tool_input?: unknown
  latency?: number
  total_token_count?: number
  aggregate_latency?: number
  aggregate_total_token_count?: number
}

export type StreamEventResponse = {
  event?: string
  data?: StreamEventData
}

export type ChatThought = {
  id: string
  position: number
  event: string
  thought: string
  observation: string
  tool: string
  tool_input: Record<string, unknown>
  latency: number
  created_at: number
}

export type StreamMessage = {
  id: string
  conversation_id: string
  answer: string
  answer_parts: unknown[]
  artifacts: unknown[]
  latency: number
  total_token_count: number
  agent_thoughts: ChatThought[]
  callable_trace_events?: CallableTraceEvent[]
}

export type RenderableStreamMessage = StreamMessage & {
  render_id: string
}

export type StreamState = {
  position: number
  message_id: string
  task_id: string
  conversation_id: string
}

export type StreamApplyResult = {
  state: StreamState
  didUpdate: boolean
}

let streamRenderIdSequence = 0

export const createChatRenderId = (scope: string = 'chat') => {
  streamRenderIdSequence += 1
  return `${scope}-${streamRenderIdSequence}`
}

export const withChatRenderId = <T extends { id?: string; render_id?: string }>(
  message: T,
  scope: string = 'chat',
): T & { render_id: string } => {
  const renderId = String(message.render_id ?? '').trim() || String(message.id ?? '').trim() || createChatRenderId(scope)
  return {
    ...message,
    render_id: renderId,
  }
}

export const withChatRenderIds = <T extends { id?: string; render_id?: string }>(
  messages: T[],
  scope: string = 'chat',
): Array<T & { render_id: string }> => {
  return messages.map((message) => withChatRenderId(message, scope))
}

export const mergeChatHistoryMessages = <T extends { id?: string; render_id?: string }>(
  messages: T[],
  scope: string = 'chat',
): Array<Omit<T, 'callable_trace_events'> & { render_id: string }> => {
  const merged: Array<Omit<T, 'callable_trace_events'> & { render_id: string }> = []
  const seenKeys = new Set<string>()

  for (const message of messages) {
    const normalizedId = String(message.id ?? '').trim()
    const normalizedRenderId = String(message.render_id ?? '').trim()
    const identityKey = normalizedId || normalizedRenderId
    if (identityKey && seenKeys.has(identityKey)) {
      continue
    }

    if (identityKey) {
      seenKeys.add(identityKey)
    }

    const historyMessage = message as T & {
      agent_thoughts?: unknown
      callable_trace_events?: unknown
    }
    const normalizedMessage = {
      ...message,
      render_id: normalizedRenderId || normalizedId || createChatRenderId(scope),
    } as Omit<T, 'callable_trace_events'> & {
      render_id: string
      agent_thoughts?: unknown[]
    }
    delete (normalizedMessage as { callable_trace_events?: unknown }).callable_trace_events

    if (Array.isArray(historyMessage.agent_thoughts)) {
      const thoughts = historyMessage.agent_thoughts.filter(
        (thought) =>
          !thought ||
          typeof thought !== 'object' ||
          Array.isArray(thought) ||
          (thought as Record<string, unknown>).event !== QueueEvent.callableTrace,
      )
      if (thoughts.length !== historyMessage.agent_thoughts.length) {
        normalizedMessage.agent_thoughts = thoughts
      }
    }

    merged.push(normalizedMessage)
  }

  return merged
}

const toPositiveNumber = (value: unknown) => {
  const normalized = Number(value)
  return Number.isFinite(normalized) && normalized > 0 ? normalized : 0
}

const toNonNegativeNumber = (value: unknown) => {
  const normalized = Number(value)
  return Number.isFinite(normalized) && normalized >= 0 ? normalized : 0
}

const normalizeToolInput = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

const buildThought = (data: StreamEventData, position: number): ChatThought => {
  return {
    id: String(data.id ?? ''),
    position,
    event: String(data.event ?? ''),
    thought: String(data.thought ?? ''),
    observation: String(data.observation ?? ''),
    tool: String(data.tool ?? ''),
    tool_input: normalizeToolInput(data.tool_input),
    latency: toPositiveNumber(data.latency),
    created_at: 0,
  }
}

const upsertThought = (
  thoughts: ChatThought[],
  data: StreamEventData,
  nextState: StreamState,
  options: { appendThought: boolean },
) => {
  const { appendThought } = options
  const eventId = String(data.id ?? '')
  const event = String(data.event ?? '')
  const thoughtIdx = thoughts.findIndex((item) => item.id === eventId && item.event === event)

  if (thoughtIdx === -1) {
    nextState.position += 1
    thoughts.push(buildThought(data, nextState.position))
    return
  }

  const previous = thoughts[thoughtIdx]
  thoughts[thoughtIdx] = {
    ...previous,
    ...buildThought(data, previous.position),
    thought: appendThought
      ? `${previous.thought}${String(data.thought ?? '')}`
      : String(data.thought ?? previous.thought ?? ''),
    observation: String(data.observation ?? previous.observation ?? ''),
    tool: String(data.tool ?? previous.tool ?? ''),
    tool_input: normalizeToolInput(data.tool_input ?? previous.tool_input),
    latency: toPositiveNumber(data.latency) || previous.latency,
  }
}

export const applyChatStreamEvent = (
  message: StreamMessage,
  eventResponse: StreamEventResponse,
  currentState: StreamState,
): StreamApplyResult => {
  const event = String(eventResponse?.event ?? '')
  const data = eventResponse?.data ?? {}
  const nextState: StreamState = { ...currentState }

  if (event === QueueEvent.callableTrace) {
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      const traceEvents = message.callable_trace_events ?? []
      if (!message.callable_trace_events) message.callable_trace_events = traceEvents
      traceEvents.push(data as CallableTraceEvent)
    }
    return { state: nextState, didUpdate: false }
  }

  if (nextState.message_id === '' && data.message_id) {
    nextState.task_id = String(data.task_id ?? '')
    nextState.message_id = String(data.message_id)
    nextState.conversation_id = String(data.conversation_id ?? '')
    message.id = nextState.message_id
    message.conversation_id = nextState.conversation_id
  }

  if (event === '' || event === QueueEvent.ping) {
    return { state: nextState, didUpdate: false }
  }

  const thoughts = message.agent_thoughts
  let shouldRefreshOutputParts = false

  if (event === QueueEvent.agentMessage) {
    upsertThought(thoughts, data, nextState, { appendThought: true })
    message.answer += String(data.thought ?? '')
    shouldRefreshOutputParts = true
  } else if (event === QueueEvent.agentAction) {
    upsertThought(thoughts, data, nextState, { appendThought: false })
    const observation = String(data.observation ?? '')
    const existingUrls = mergeChatArtifacts([], message.artifacts)
      .map(artifact => String(artifact.url || '').trim())
    const inlineImageUrls = extractInlineImageUrls(observation, existingUrls)
    if (inlineImageUrls.length > 0) {
      const extractedArtifacts = inlineImageUrls.map((url, index) => ({
        name: inlineImageUrls.length === 1 ? '生成图片' : `生成图片 ${index + 1}`,
        url,
      }))
      message.artifacts = mergeChatArtifacts(message.artifacts, extractedArtifacts)
      shouldRefreshOutputParts = true
    }
  } else if (event === QueueEvent.deepThinking) {
    upsertThought(thoughts, data, nextState, { appendThought: true })
  } else if (
    event === QueueEvent.deepStep ||
    event === QueueEvent.deepComplete
  ) {
    upsertThought(thoughts, data, nextState, { appendThought: false })
  } else if (event === QueueEvent.deepArtifactCreated) {
    upsertThought(thoughts, data, nextState, { appendThought: false })
    const toolInput = (data.tool_input && typeof data.tool_input === 'object')
      ? data.tool_input as Record<string, unknown>
      : {}
    message.artifacts = mergeChatArtifacts(message.artifacts, [toolInput.artifact || null])
    shouldRefreshOutputParts = true
  } else if (event === QueueEvent.error) {
    message.answer = String(data.observation ?? '')
    shouldRefreshOutputParts = true
  } else if (event === QueueEvent.timeout) {
    message.answer = '当前Agent执行已超时，无法得到答案，请重试'
    shouldRefreshOutputParts = true
  } else {
    nextState.position += 1
    thoughts.push(buildThought(data, nextState.position))
  }

  const normalizedLatency = toPositiveNumber(
    data.aggregate_latency ?? data.latency,
  )
  if (normalizedLatency > 0) {
    message.latency = normalizedLatency
  }

  const normalizedTokenCount = Math.floor(toNonNegativeNumber(
    data.aggregate_total_token_count ?? data.total_token_count,
  ))
  if (normalizedTokenCount > 0) {
    message.total_token_count = normalizedTokenCount
  }

  message.agent_thoughts = thoughts
  if (shouldRefreshOutputParts) {
    message.answer_parts = buildChatOutputParts(message.answer, message.artifacts)
  }
  return { state: nextState, didUpdate: true }
}

