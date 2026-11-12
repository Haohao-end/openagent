import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChatMessageTimeline from '../ChatMessageTimeline.vue'

const dynamicScrollerStub = {
  props: ['items', 'keyField'],
  template:
    '<div class="dynamic-scroller-stub" :data-key-field="keyField"><template v-for="(item, index) in items" :key="item.render_id || item.id || index"><slot :item="item" :active="true" /></template></div>',
}

const dynamicScrollerItemStub = {
  props: ['item', 'active', 'sizeDependencies'],
  template:
    '<div class="dynamic-scroller-item-stub" :data-size-dependencies="JSON.stringify(sizeDependencies)"><slot /></div>',
}

describe('ChatMessageTimeline', () => {
  it('passes layout-sensitive size dependencies to the virtual scroller items', async () => {
    const traceEvents = [
      { event_id: 'trace-1', run_id: 'run-1', phase: 'start', inputs: { prompt: 'trace' } },
    ]
    const wrapper = shallowMount(ChatMessageTimeline, {
      props: {
        messages: [
          {
            id: 'message-1',
            render_id: 'render-message-1',
            conversation_id: 'conversation-1',
            query: '请总结这张图',
            image_urls: ['https://example.com/image-a.png'],
            answer: '第一版回答',
            answer_parts: [{ type: 'text', text: '第一版回答' }],
            artifacts: [{ name: 'plan.docx', url: 'https://example.com/plan.docx' }],
            callable_trace_events: traceEvents,
            total_token_count: 12,
            latency: 1.2,
            agent_thoughts: [
              {
                id: 'thought-1',
                event: 'deepStep',
                thought: '正在整理步骤',
                observation: '',
                tool: 'write_todos',
                tool_input: {
                  timeline: {
                    title: '整理步骤',
                  },
                },
                latency: 1,
                created_at: 0,
              },
            ],
            created_at: 1710000000,
            suggested_questions: ['继续'],
          },
        ] as any,
        account: {
          name: 'Tester',
          avatar: '',
        },
        app: {
          name: 'OpenAgent',
          icon: '',
        },
        loading: false,
        textToSpeechEnable: true,
      },
      global: {
        stubs: {
          'dynamic-scroller': dynamicScrollerStub,
          'dynamic-scroller-item': dynamicScrollerItemStub,
          'human-message': true,
          'ai-message': {
            props: ['callable_trace_events'],
            template: '<div class="ai-message-stub" :data-traces="JSON.stringify(callable_trace_events)" />',
          },
        },
      },
    })

    const sizeDependencies = JSON.parse(
      wrapper.get('.dynamic-scroller-item-stub').attributes('data-size-dependencies') || '[]',
    )

    expect(wrapper.get('.dynamic-scroller-stub').attributes('data-key-field')).toBe('render_id')
    expect(sizeDependencies).toHaveLength(9)
    expect(sizeDependencies[0]).toBe('请总结这张图')
    expect(sizeDependencies[1]).toContain('https://example.com/image-a.png')
    expect(sizeDependencies[2]).toBe('第一版回答')
    expect(sizeDependencies[4]).toContain('plan.docx')
    expect(sizeDependencies[5]).toContain('正在整理步骤')
    expect(sizeDependencies[6]).not.toContain('trace')
    expect(sizeDependencies[7]).toContain('继续')
    expect(sizeDependencies[8]).toBe(0)
    expect(JSON.parse(wrapper.get('.ai-message-stub').attributes('data-traces') || '[]')).toEqual(
      traceEvents,
    )
  })
})
