import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import HumanMessage from '../HumanMessage.vue'

vi.mock('@/utils/clipboard', () => ({
  copyTextToClipboard: vi.fn(),
}))

vi.mock('@/utils/helper', () => ({
  getUserAvatarUrl: () => '',
}))

describe('HumanMessage.vue', () => {
  const mountHumanMessage = (props: Record<string, unknown> = {}) =>
    mount(HumanMessage, {
      props: {
        account: {
          name: '用户',
          avatar: '',
        },
        query: '这是一段非常长的用户消息内容 '.repeat(20),
        image_urls: [],
        ...props,
      },
      global: {
        stubs: {
          'a-avatar': {
            props: ['imageUrl', 'size', 'shape'],
            template: '<div class="avatar-stub" :data-image-url="imageUrl"><slot /></div>',
          },
          'a-image': {
            props: ['src'],
            template: '<img class="image-stub" :src="src" />',
          },
          'icon-copy': true,
        },
      },
    })

  it('constrains the message bubble to the available chat column width', () => {
    const wrapper = mountHumanMessage()

    const bubble = wrapper.get('.message-bubble-content')
    const bubbleClasses = bubble.classes()

    expect(wrapper.get('.justify-end').classes()).toEqual(
      expect.arrayContaining(['max-w-full', 'min-w-0']),
    )
    expect(bubbleClasses).toContain('message-bubble-content')
    expect(bubbleClasses).not.toContain('max-w-[600px]')
  })
})
