import { QueueEvent } from '@/config'

type StreamEventData = {
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
  tool_input: unknown
  latency: number
  created_at: number
}

export type StreamMessage = {
  id: string
  conversation_id: string
  answer: string
  latency: number
  total_token_count: number
  agent_thoughts: ChatThought[]
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

const toPositiveNumber = (value: unknown) => {
  const normalized = Number(value)
  return Number.isFinite(normalized) && normalized > 0 ? normalized : 0
}

const toNonNegativeNumber = (value: unknown) => {
  const normalized = Number(value)
  return Number.isFinite(normalized) && normalized >= 0 ? normalized : 0
}

const buildThought = (data: StreamEventData, position: number): ChatThought => {
  return {
    id: String(data.id ?? ''),
    position,
    event: String(data.event ?? ''),
    thought: String(data.thought ?? ''),
    observation: String(data.observation ?? ''),
    tool: String(data.tool ?? ''),
    tool_input: data.tool_input ?? {},
    latency: toPositiveNumber(data.latency),
    created_at: 0,
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
  if (event === QueueEvent.agentMessage) {
    const eventId = String(data.id ?? '')
    const thoughtIdx = thoughts.findIndex((item) => item.id === eventId)
    if (thoughtIdx === -1) {
      nextState.position += 1
      thoughts.push(buildThought(data, nextState.position))
    } else {
      thoughts[thoughtIdx] = {
        ...thoughts[thoughtIdx],
        thought: `${thoughts[thoughtIdx].thought}${String(data.thought ?? '')}`,
        latency: toPositiveNumber(data.latency),
      }
    }
    message.answer += String(data.thought ?? '')
  } else if (event === QueueEvent.error) {
    message.answer = String(data.observation ?? '')
  } else if (event === QueueEvent.timeout) {
    message.answer = '当前Agent执行已超时，无法得到答案，请重试'
  } else {
    nextState.position += 1
    thoughts.push(buildThought(data, nextState.position))
  }

  const normalizedLatency = toPositiveNumber(data.latency)
  if (normalizedLatency > 0) {
    message.latency = normalizedLatency
  }

  const normalizedTokenCount = Math.floor(toNonNegativeNumber(data.total_token_count))
  if (normalizedTokenCount > 0) {
    message.total_token_count = normalizedTokenCount
  }

  message.agent_thoughts = thoughts
  return { state: nextState, didUpdate: true }
}
