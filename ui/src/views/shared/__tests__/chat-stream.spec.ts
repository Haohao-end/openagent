import { describe, expect, it } from 'vitest'
import { QueueEvent } from '@/config'
import {
  applyChatStreamEvent,
  type StreamEventResponse,
  type StreamMessage,
  type StreamState,
} from '@/views/shared/chat-stream'

const createMessage = (): StreamMessage => ({
  id: '',
  conversation_id: '',
  answer: '',
  latency: 0,
  total_token_count: 0,
  agent_thoughts: [],
})

const createState = (): StreamState => ({
  position: 0,
  message_id: '',
  task_id: '',
  conversation_id: '',
})

describe('chat-stream', () => {
  it('appends agent message content and initializes ids', () => {
    const message = createMessage()
    const state = createState()
    const event: StreamEventResponse = {
      event: QueueEvent.agentMessage,
      data: {
        id: 'event-1',
        event: QueueEvent.agentMessage,
        thought: '你好',
        message_id: 'message-1',
        task_id: 'task-1',
        conversation_id: 'conversation-1',
        latency: 1.2,
        total_token_count: 21,
      },
    }

    const result = applyChatStreamEvent(message, event, state)

    expect(result.didUpdate).toBe(true)
    expect(result.state.position).toBe(1)
    expect(result.state.message_id).toBe('message-1')
    expect(result.state.task_id).toBe('task-1')
    expect(result.state.conversation_id).toBe('conversation-1')
    expect(message.id).toBe('message-1')
    expect(message.conversation_id).toBe('conversation-1')
    expect(message.answer).toBe('你好')
    expect(message.latency).toBe(1.2)
    expect(message.total_token_count).toBe(21)
    expect(message.agent_thoughts).toHaveLength(1)
  })

  it('concatenates thought chunks for same event id', () => {
    const message = createMessage()
    let state = createState()

    const firstChunk: StreamEventResponse = {
      event: QueueEvent.agentMessage,
      data: {
        id: 'event-1',
        event: QueueEvent.agentMessage,
        thought: 'Hello',
      },
    }
    const secondChunk: StreamEventResponse = {
      event: QueueEvent.agentMessage,
      data: {
        id: 'event-1',
        event: QueueEvent.agentMessage,
        thought: ' World',
      },
    }

    state = applyChatStreamEvent(message, firstChunk, state).state
    const secondResult = applyChatStreamEvent(message, secondChunk, state)

    expect(secondResult.state.position).toBe(1)
    expect(message.answer).toBe('Hello World')
    expect(message.agent_thoughts).toHaveLength(1)
    expect(message.agent_thoughts[0].thought).toBe('Hello World')
  })

  it('overwrites answer on error event', () => {
    const message = createMessage()
    message.answer = 'previous'

    const result = applyChatStreamEvent(
      message,
      {
        event: QueueEvent.error,
        data: { observation: '执行失败' },
      },
      createState(),
    )

    expect(result.didUpdate).toBe(true)
    expect(message.answer).toBe('执行失败')
  })

  it('sets timeout fallback message on timeout event', () => {
    const message = createMessage()

    applyChatStreamEvent(
      message,
      {
        event: QueueEvent.timeout,
        data: {},
      },
      createState(),
    )

    expect(message.answer).toBe('当前Agent执行已超时，无法得到答案，请重试')
  })
})
