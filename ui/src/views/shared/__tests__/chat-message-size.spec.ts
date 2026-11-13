import { describe, expect, it } from 'vitest'
import { buildChatMessageSizeDependencies } from '../chat-message-size'

describe('chat-message-size', () => {
  it('changes the layout signature when content that affects height changes', () => {
    const base = buildChatMessageSizeDependencies({
      query: '请总结这张图',
      image_urls: ['https://example.com/image-a.png'],
      answer: '第一版回答',
      answer_parts: [{ type: 'text', text: '第一版回答' }],
      artifacts: [{ name: 'plan.docx', url: 'https://example.com/plan.docx' }],
      callable_trace_events: [
        { event_id: 'trace-start', run_id: 'run-1', phase: 'start', inputs: { prompt: 'private' } },
      ],
      agent_thoughts: [
        {
          id: 'thought-1',
          event: 'deepStep',
          thought: '正在整理步骤',
          tool: 'write_todos',
          tool_input: {
            timeline: {
              title: '整理步骤',
            },
          },
        },
      ],
      suggested_questions: ['继续'],
    })

    const updated = buildChatMessageSizeDependencies({
      query: '请总结这张图',
      image_urls: ['https://example.com/image-a.png'],
      answer: '第一版回答',
      answer_parts: [{ type: 'text', text: '第一版回答' }],
      artifacts: [{ name: 'plan.docx', url: 'https://example.com/plan.docx' }],
      callable_trace_events: [
        { event_id: 'trace-end', run_id: 'run-1', phase: 'end', outputs: { answer: 'done' } },
      ],
      agent_thoughts: [
        {
          id: 'thought-1',
          event: 'deepStep',
          thought: '正在整理更完整的步骤说明',
          tool: 'write_todos',
          tool_input: {
            timeline: {
              title: '整理步骤',
            },
          },
        },
      ],
      suggested_questions: ['继续'],
    })

    expect(base).toHaveLength(9)
    expect(updated).toHaveLength(9)
    expect(base).not.toEqual(updated)
    expect(base[6]).not.toBe(updated[6])
    expect(base[6]).not.toContain('private')
    expect(base[7]).toContain('继续')
    expect(base[8]).toBe(0)
    expect(buildChatMessageSizeDependencies({ query: 'x' }, true)[8]).toBe(1)
  })
})
