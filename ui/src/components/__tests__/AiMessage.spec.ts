import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

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
        stubs: {
          AgentThought: true,
          DotFlashing: true,
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
})
