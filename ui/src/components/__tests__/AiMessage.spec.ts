import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { QueueEvent } from '@/config'
import { createTestI18n } from '@/i18n'

import AiMessage from '../AiMessage.vue'

vi.mock('@/hooks/use-audio', () => ({
  useAudioPlayer: () => ({
    messageAudioLoading: { value: false },
    thoughtAudioLoading: { value: false },
    isPlaying: { value: false },
    activeMessageId: { value: '' },
    activeThoughtId: { value: '' },
    activeStreamType: { value: '' },
    startAudioStream: vi.fn(),
    startTextAudioStream: vi.fn(),
    stopAudioStream: vi.fn(),
  }),
}))

vi.mock('@/hooks/use-markdown-renderer', () => ({
  useMarkdownRenderer: () => ({
    renderMarkdown: (value: string) => value,
    handleMarkdownCopyClick: vi.fn(),
  }),
}))

describe('AiMessage.vue', () => {
  const mountAiMessage = (props: Record<string, unknown> = {}) =>
    mount(AiMessage, {
      props: {
        app: {
          name: 'OpenAgent',
          avatar_text: 'OpenAgent',
        },
        answer: '欢迎使用 OpenAgent',
        agent_thoughts: [],
        ...props,
      },
      global: {
        plugins: [createTestI18n('zh-CN')],
        stubs: {
          AgentThought: true,
          DotFlashing: true,
          'a-image': {
            props: ['src', 'preview'],
            template: '<div class="image-stub" :data-src="src"></div>',
          },
          'a-avatar': {
            props: ['imageUrl', 'size', 'shape'],
            template: '<div class="avatar-stub" :data-image-url="imageUrl"><slot /></div>',
          },
          'a-space': { template: '<div><slot /></div>' },
          'a-divider': true,
          'icon-apps': true,
          'icon-check': true,
          'icon-copy': true,
          'icon-loading': true,
          'icon-pause': true,
          'icon-play-circle': true,
        },
      },
    })

  it('renders the OpenAgent full-text avatar when avatar_text is provided', () => {
    const wrapper = mountAiMessage()

    expect(wrapper.find('.avatar-stub').text()).toBe('OpenAgent')
    expect(wrapper.text()).toContain('OpenAgent')
    expect(wrapper.find('.avatar-stub').attributes('data-image-url')).toBeUndefined()
  })

  it('constrains the answer bubble to the available chat column width', () => {
    const wrapper = mountAiMessage({
      answer: '这是一段非常长的 AI 输出内容 '.repeat(20),
    })

    const root = wrapper.get('.group')
    const bubble = wrapper.get('.message-bubble-content')
    const bubbleClasses = bubble.classes()

    expect(root.classes()).toEqual(expect.arrayContaining(['max-w-full', 'min-w-0']))
    expect(bubbleClasses).toContain('message-bubble-content')
    expect(bubbleClasses).toContain('markdown-body')
    expect(bubbleClasses).not.toContain('max-w-[600px]')
  })

  it('uses the same width contract for the loading bubble', () => {
    const wrapper = mountAiMessage({
      answer: '',
      loading: true,
    })

    const bubble = wrapper.get('.message-bubble-content')

    expect(bubble.classes()).toContain('message-bubble-content')
    expect(bubble.classes()).not.toContain('max-w-[600px]')
  })

  it('renders the deep agent timeline when deep step thoughts exist', () => {
    const wrapper = mountAiMessage({
      agent_thoughts: [
        {
          id: 'step-1',
          event: QueueEvent.deepStep,
          thought: '已规划任务：收集景点 / 规划行程',
          tool: 'write_todos',
          tool_input: {
            timeline: {
              step_type: 'plan',
              status: 'success',
              title: '拆解任务',
              detail: '已规划任务：收集景点 / 规划行程',
            },
          },
          latency: 1.8,
        },
      ],
    })

    expect(wrapper.find('.deep-agent-timeline').exists()).toBe(true)
    expect(wrapper.text()).toContain('拆解任务')
    expect(wrapper.text()).toContain('已规划任务：收集景点 / 规划行程')
  })

  it('renders callable traces in regular agent messages with hierarchy and expandable details', async () => {
    const wrapper = mountAiMessage({
      callable_trace_events: [
        {
          schema_version: 1,
          event_id: 'chain-start',
          run_id: 'chain-1',
          run_type: 'chain',
          phase: 'start',
          name: 'AgentChain',
          status: 'running',
          inputs: { query: 'find a place' },
        },
        {
          schema_version: 1,
          event_id: 'llm-end',
          run_id: 'llm-1',
          parent_run_id: 'chain-1',
          run_type: 'llm',
          phase: 'end',
          name: 'ChatOpenAI',
          status: 'succeeded',
          outputs: { answer: 'done' },
          latency_ms: 42,
        },
        {
          schema_version: 1,
          event_id: 'tool-error',
          run_id: 'tool-1',
          parent_run_id: 'chain-1',
          run_type: 'tool',
          phase: 'error',
          name: 'Search',
          status: 'failed',
          error: 'Search timed out',
        },
        {
          schema_version: 1,
          event_id: 'retriever-end',
          run_id: 'retriever-1',
          parent_run_id: 'chain-1',
          run_type: 'retriever',
          phase: 'end',
          name: 'VectorRetriever',
          status: 'succeeded',
          latency_ms: 18,
        },
      ],
    })

    const timeline = wrapper.get('[data-testid="callable-trace-timeline"]')
    const calls = wrapper.findAll('[data-testid="callable-trace-call"]')
    expect(timeline.text()).toContain('Callable 调用时间线')
    expect(calls).toHaveLength(4)
    expect(calls[0].text()).toContain('Chain')
    expect(calls[0].attributes('data-status')).toBe('running')
    expect(calls[1].text()).toContain('LLM')
    expect(calls[1].attributes('data-parent-run-id')).toBe('chain-1')
    expect(calls[1].text()).toContain('42 ms')
    expect(calls[2].text()).toContain('Tool')
    expect(calls[2].attributes('data-status')).toBe('failed')
    expect(calls[3].text()).toContain('检索器')

    const inputDetails = calls[0].get('details')
    await inputDetails.get('summary').trigger('click')
    expect((inputDetails.element as HTMLDetailsElement).open).toBe(true)
    expect(inputDetails.text()).toContain('find a place')
    expect(calls[1].get('[data-testid="callable-trace-output"]').text()).toContain('done')
    expect(calls[2].get('[data-testid="callable-trace-error"]').text()).toContain(
      'Search timed out',
    )
  })

  it('renders image previews inside the deep agent timeline for image artifacts', () => {
    const wrapper = mountAiMessage({
      answer: '',
      answer_parts: [],
      agent_thoughts: [
        {
          id: 'artifact-1',
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
      ],
    })

    expect(wrapper.find('.deep-agent-timeline').exists()).toBe(true)
    expect(wrapper.find('.chat-image-gallery').exists()).toBe(true)
    expect(wrapper.find('.image-stub').attributes('data-src')).toBe('https://example.com/cover.png')
    expect(wrapper.text()).toContain('生成图片')
    expect(wrapper.text()).toContain('png · image/png')
  })

  it('falls back to the legacy deep thinking panel when only deep_thinking exists', () => {
    const wrapper = mountAiMessage({
      agent_thoughts: [
        {
          id: 'deep-1',
          event: QueueEvent.deepThinking,
          thought: '先分析约束，再拆解步骤',
          latency: 1.8,
        },
      ],
    })

    expect(wrapper.find('.deep-thinking-panel').exists()).toBe(true)
    expect(wrapper.text()).toContain('先分析约束，再拆解步骤')
  })

  it('renders image and artifact parts from the unified multimodal output protocol', async () => {
    const wrapper = mountAiMessage({
      answer: '已生成图片与附件',
      answer_parts: [
        { type: 'text', text: '已生成图片与附件' },
        { type: 'image', url: 'https://example.com/cover.png', name: 'cover.png' },
        { type: 'image', url: 'https://example.com/detail.png', name: 'detail.png' },
        { type: 'artifact', url: 'https://example.com/plan.docx', name: 'plan.docx', extension: 'docx' },
      ],
    })

    expect(wrapper.find('.chat-image-gallery').exists()).toBe(true)
    expect(wrapper.find('.image-stub').attributes('data-src')).toBe('https://example.com/cover.png')
    expect(wrapper.findAll('.chat-image-gallery__thumb')).toHaveLength(2)
    expect(wrapper.text()).toContain('1/2')

    await wrapper.findAll('.chat-image-gallery__thumb')[1].trigger('click')

    expect(wrapper.find('.image-stub').attributes('data-src')).toBe('https://example.com/detail.png')
    expect(wrapper.find('.message-artifact-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('plan.docx')
    expect(wrapper.text()).toContain('下载附件')
  })

  it('renders one unified gallery for images from different groups', async () => {
    const wrapper = mountAiMessage({
      answer: '已生成两组穿搭图',
      answer_parts: [
        { type: 'text', text: '已生成两组穿搭图' },
        { type: 'image', url: 'https://example.com/1.png', name: 'look-1.png', group_id: 'batch-a', group_name: '通勤穿搭' },
        { type: 'image', url: 'https://example.com/2.png', name: 'look-2.png', group_id: 'batch-a', group_name: '通勤穿搭' },
        { type: 'image', url: 'https://example.com/3.png', name: 'look-3.png', group_id: 'batch-b', group_name: '雨天穿搭' },
      ],
    })

    const galleries = wrapper.findAll('.chat-image-gallery')
    expect(galleries).toHaveLength(1)
    expect(galleries[0].text()).toContain('1/3')
    expect(wrapper.findAll('.chat-image-gallery__thumb')).toHaveLength(3)

    await wrapper.findAll('.chat-image-gallery__thumb')[2].trigger('click')

    expect(wrapper.find('.image-stub').attributes('data-src')).toBe('https://example.com/3.png')
  })
})
