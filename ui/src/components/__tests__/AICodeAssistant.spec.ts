import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { expect, it, vi } from 'vitest'
import AICodeAssistant from '../AICodeAssistant.vue'

const { codeAssistantChat } = vi.hoisted(() => ({ codeAssistantChat: vi.fn() }))
vi.mock('@/services/ai', () => ({ codeAssistantChat }))
vi.mock('@/hooks/use-markdown-renderer', () => ({ useMarkdownRenderer: () => ({ renderMarkdown: (value: string) => value, handleMarkdownCopyClick: vi.fn() }) }))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: vi.fn(), warning: vi.fn(), success: vi.fn() } }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ locale: { value: 'en-US' } }) }))

const ButtonStub = defineComponent({ emits: ['click'], setup(_props, { emit, slots }) { return () => h('button', { onClick: () => emit('click') }, slots.default?.()) } })

it('aborts and ignores a stream after closing and reopening', async () => {
  codeAssistantChat.mockReset()
  let onData!: (event: { data?: { content?: string } }) => void
  let signal: AbortSignal | undefined
  codeAssistantChat.mockImplementation((_question, callback, requestSignal) => {
    onData = callback
    signal = requestSignal
    return new Promise((resolve, reject) => {
      const timer = setTimeout(resolve, 1000)
      requestSignal?.addEventListener('abort', () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')) })
    })
  })
  const wrapper = mount(AICodeAssistant, { attachTo: document.body, props: { visible: true }, global: { stubs: { '*': true, 'a-button': ButtonStub } } })
  const input = document.body.querySelector('input')!
  input.value = 'generate a helper'
  input.dispatchEvent(new Event('input', { bubbles: true }))
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
  await flushPromises()
  document.body.querySelector('button')!.click()
  await wrapper.setProps({ visible: false }); await wrapper.setProps({ visible: true })
  onData({ data: { content: 'stale response' } })
  await flushPromises()
  expect(document.body.textContent).not.toContain('stale response')
  expect(signal?.aborted).toBe(true)
  expect(document.body.textContent).not.toContain('AI is generating code...')
  wrapper.unmount()
})
