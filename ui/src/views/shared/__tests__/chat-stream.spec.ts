import { describe, expect, it } from 'vitest'
import { QueueEvent } from '@/config'
import {
  applyChatStreamEvent,
  mergeChatHistoryMessages,
  withChatRenderId,
  type StreamEventResponse,
  type StreamMessage,
  type StreamState,
} from '@/views/shared/chat-stream'

const createMessage = (): StreamMessage => ({
  id: '',
  conversation_id: '',
  answer: '',
  answer_parts: [],
  artifacts: [],
  latency: 0,
  total_token_count: 0,
  agent_thoughts: [],
  callable_trace_events: [],
})

const createState = (): StreamState => ({
  position: 0,
  message_id: '',
  task_id: '',
  conversation_id: '',
})

describe('chat-stream', () => {
  it('stores callable traces separately without updating regular chat state', () => {
    const message = createMessage()
    const state = createState()
    const trace = {
      schema_version: 1,
      event_id: 'trace-event-1',
      run_id: 'trace-run-1',
      parent_run_id: 'trace-parent-1',
      phase: 'end',
      run_type: 'llm',
      latency_ms: 34.5,
    }

    const result = applyChatStreamEvent(
      message,
      { event: QueueEvent.callableTrace, data: trace } as StreamEventResponse,
      state,
    )

    expect(result.didUpdate).toBe(false)
    expect(result.state).toEqual(state)
    expect(message.callable_trace_events).toEqual([trace])
    expect(message.agent_thoughts).toEqual([])
    expect(message.answer).toBe('')
  })

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

  it('prefers aggregate metrics for message-level latency and token count', () => {
    const message = createMessage()

    applyChatStreamEvent(
      message,
      {
        event: QueueEvent.deepComplete,
        data: {
          id: 'deep-complete-1',
          event: QueueEvent.deepComplete,
          thought: '整理执行结果',
          latency: 20,
          total_token_count: 120,
          aggregate_latency: 25,
          aggregate_total_token_count: 150,
        },
      },
      createState(),
    )

    expect(message.agent_thoughts).toHaveLength(1)
    expect(message.agent_thoughts[0].latency).toBe(20)
    expect(message.latency).toBe(25)
    expect(message.total_token_count).toBe(150)
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

  it('keeps deep thinking chunks separate from agent message chunks', () => {
    const message = createMessage()
    let state = createState()

    const deepThinkingChunk: StreamEventResponse = {
      event: QueueEvent.deepThinking,
      data: {
        id: 'deep-1',
        event: QueueEvent.deepThinking,
        thought: '先拆解任务',
      },
    }
    const deepThinkingChunk2: StreamEventResponse = {
      event: QueueEvent.deepThinking,
      data: {
        id: 'deep-1',
        event: QueueEvent.deepThinking,
        thought: '，再执行',
      },
    }

    state = applyChatStreamEvent(message, deepThinkingChunk, state).state
    const secondResult = applyChatStreamEvent(message, deepThinkingChunk2, state)

    expect(secondResult.state.position).toBe(1)
    expect(message.answer).toBe('')
    expect(message.agent_thoughts).toHaveLength(1)
    expect(message.agent_thoughts[0].event).toBe(QueueEvent.deepThinking)
    expect(message.agent_thoughts[0].thought).toBe('先拆解任务，再执行')
  })

  it('upserts deep step events by id instead of appending duplicate rows', () => {
    const message = createMessage()
    let state = createState()

    const firstStep: StreamEventResponse = {
      event: QueueEvent.deepStep,
      data: {
        id: 'step-1',
        event: QueueEvent.deepStep,
        thought: '正在执行代码',
        tool: 'execute',
        tool_input: {
          timeline: {
            step_type: 'tool',
            status: 'start',
            title: '执行代码',
            detail: 'python3 run.py',
          },
        },
      },
    }
    const secondStep: StreamEventResponse = {
      event: QueueEvent.deepStep,
      data: {
        id: 'step-1',
        event: QueueEvent.deepStep,
        thought: '执行完成',
        observation: 'exit_code=0',
        tool: 'execute',
        tool_input: {
          timeline: {
            step_type: 'tool',
            status: 'success',
            title: '执行代码',
            detail: '执行完成',
          },
        },
        latency: 2.4,
      },
    }

    state = applyChatStreamEvent(message, firstStep, state).state
    const result = applyChatStreamEvent(message, secondStep, state)

    expect(result.state.position).toBe(1)
    expect(message.agent_thoughts).toHaveLength(1)
    expect(message.agent_thoughts[0].thought).toBe('执行完成')
    expect(message.agent_thoughts[0].observation).toBe('exit_code=0')
    expect(message.agent_thoughts[0].latency).toBe(2.4)
  })

  it('records artifact created events as separate timeline items', () => {
    const message = createMessage()

    const result = applyChatStreamEvent(
      message,
      {
        event: QueueEvent.deepArtifactCreated,
        data: {
          id: 'artifact-1',
          event: QueueEvent.deepArtifactCreated,
          thought: 'trip-plan.docx',
          tool: 'artifact',
          tool_input: {
            artifact: {
              name: 'trip-plan.docx',
              url: 'https://example.com/trip-plan.docx',
            },
          },
        },
      },
      createState(),
    )

    expect(result.didUpdate).toBe(true)
    expect(message.agent_thoughts).toHaveLength(1)
    expect(message.agent_thoughts[0].event).toBe(QueueEvent.deepArtifactCreated)
    expect((message.agent_thoughts[0].tool_input as any).artifact.name).toBe('trip-plan.docx')
    expect(message.artifacts).toEqual([
      {
        name: 'trip-plan.docx',
        url: 'https://example.com/trip-plan.docx',
      },
    ])
    expect(message.answer_parts).toEqual([
      {
        type: 'artifact',
        name: 'trip-plan.docx',
        url: 'https://example.com/trip-plan.docx',
      },
    ])
  })

  it('records image artifact created events as image answer parts', () => {
    const message = createMessage()

    applyChatStreamEvent(
      message,
      {
        event: QueueEvent.deepArtifactCreated,
        data: {
          id: 'artifact-image-1',
          event: QueueEvent.deepArtifactCreated,
          thought: 'cover.png',
          tool: 'artifact',
          tool_input: {
            artifact: {
              name: 'cover.png',
              url: 'https://example.com/cover.png',
              extension: 'png',
              mime_type: 'image/png',
            },
          },
        },
      },
      createState(),
    )

    expect(message.artifacts).toEqual([
      {
        name: 'cover.png',
        url: 'https://example.com/cover.png',
        extension: 'png',
        mime_type: 'image/png',
      },
    ])
    expect(message.answer_parts).toEqual([
      {
        type: 'image',
        url: 'https://example.com/cover.png',
        name: 'cover.png',
        mime_type: 'image/png',
        extension: 'png',
      },
    ])
  })

  it('promotes inline image urls from agent action observations into gallery artifacts', () => {
    const message = createMessage()

    applyChatStreamEvent(
      message,
      {
        event: QueueEvent.agentAction,
        data: {
          id: 'tool-action-1',
          event: QueueEvent.agentAction,
          thought: '正在生成图片',
          observation: '✓ 成功生成图像\n图片 1:\n  URL: https://example.com/generated.png\n  提示: 图片已持久化保存，可直接访问和引用',
          tool: 'qwen_image_text_to_image',
          tool_input: {
            prompt: '上海历史建筑',
          },
        },
      },
      createState(),
    )

    expect(message.artifacts).toEqual([
      {
        name: '生成图片',
        url: 'https://example.com/generated.png',
      },
    ])
    expect(message.answer_parts).toEqual([
      {
        type: 'image',
        url: 'https://example.com/generated.png',
        name: '生成图片',
      },
    ])
  })

  it('extracts image parts from streamed answer text when only a URL is returned', () => {
    const message = createMessage()

    applyChatStreamEvent(
      message,
      {
        event: QueueEvent.agentMessage,
        data: {
          id: 'event-image',
          event: QueueEvent.agentMessage,
          thought: '图片 1:\n  URL: https://example.com/generated',
        },
      },
      createState(),
    )

    expect(message.answer_parts).toEqual([
      {
        type: 'text',
        text: '图片 1:\n  URL: https://example.com/generated',
      },
      {
        type: 'image',
        url: 'https://example.com/generated',
      },
    ])
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

  it('keeps render ids stable while preserving backend ids when available', () => {
    const tempMessage = withChatRenderId(createMessage(), 'debug-chat')
    const historyMessage = withChatRenderId(
      {
        ...createMessage(),
        id: 'message-1',
      },
      'debug-chat',
    )

    expect(tempMessage.render_id).toMatch(/^debug-chat-/)
    expect(historyMessage.render_id).toBe('message-1')
    expect(tempMessage.render_id).not.toBe(historyMessage.render_id)
  })

  it('merges overlapping history pages by message id without duplicating rows', () => {
    const firstPage = [
      withChatRenderId(
        {
          ...createMessage(),
          id: 'message-2',
        },
        'debug-chat',
      ),
      withChatRenderId(
        {
          ...createMessage(),
          id: 'message-1',
        },
        'debug-chat',
      ),
    ]
    const overlappingPage = [
      {
        ...createMessage(),
        id: 'message-1',
        render_id: 'stale-render-id',
      } as StreamMessage & { render_id: string },
      {
        ...createMessage(),
        id: 'message-0',
        render_id: 'older-render-id',
      } as StreamMessage & { render_id: string },
    ]

    const merged = mergeChatHistoryMessages([...firstPage, ...overlappingPage], 'debug-chat')

    expect(merged.map((item) => item.id)).toEqual(['message-2', 'message-1', 'message-0'])
    expect(merged.map((item) => item.render_id)).toEqual([
      'message-2',
      'message-1',
      'older-render-id',
    ])
  })
})
