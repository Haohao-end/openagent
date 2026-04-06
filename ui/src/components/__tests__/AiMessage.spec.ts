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
  it('renders the OpenAgent full-text avatar when avatar_text is provided', () => {
    const wrapper = mount(AiMessage, {
      props: {
        app: {
          name: 'OpenAgent',
          avatar_text: 'OpenAgent',
        },
        answer: '欢迎使用 OpenAgent',
        agent_thoughts: [],
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

    expect(wrapper.find('.avatar-stub').text()).toBe('OpenAgent')
    expect(wrapper.text()).toContain('OpenAgent')
    expect(wrapper.find('.avatar-stub').attributes('data-image-url')).toBeUndefined()
  })
})
