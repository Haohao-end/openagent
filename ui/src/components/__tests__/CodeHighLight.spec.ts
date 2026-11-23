import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import CodeHighLight from '../CodeHighLight.vue'
import { copyTextToClipboard } from '@/utils/clipboard'
import { Message } from '@arco-design/web-vue'

vi.mock('@/utils/clipboard', () => ({
  copyTextToClipboard: vi.fn(),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

describe('CodeHighLight.vue', () => {
  it('copies code content using clipboard utility and shows success feedback', async () => {
    vi.mocked(copyTextToClipboard).mockResolvedValueOnce(undefined)
    const wrapper = mount(CodeHighLight, {
      props: { language: 'javascript', copyable: true },
      slots: { default: 'const greeting = "hello";' },
    })

    const button = wrapper.find('button')
    expect(button.exists()).toBe(true)
    await button.trigger('click')

    expect(copyTextToClipboard).toHaveBeenCalledWith('const greeting = "hello";')
    expect(Message.success).toHaveBeenCalledWith('chat.messages.codeCopied')
  })

  it('shows error feedback when clipboard copy rejects', async () => {
    vi.mocked(copyTextToClipboard).mockRejectedValueOnce(new Error('copy denied'))
    const wrapper = mount(CodeHighLight, {
      props: { language: 'python', copyable: true },
      slots: { default: 'print("error")' },
    })

    await wrapper.find('button').trigger('click')

    expect(copyTextToClipboard).toHaveBeenCalledWith('print("error")')
    expect(Message.error).toHaveBeenCalledWith('chat.messages.copyFailed')
  })

  it('does not render copy button when copyable is false', () => {
    const wrapper = mount(CodeHighLight, {
      props: { language: 'json', copyable: false },
      slots: { default: '{"key": "value"}' },
    })

    expect(wrapper.find('button').exists()).toBe(false)
  })
})
