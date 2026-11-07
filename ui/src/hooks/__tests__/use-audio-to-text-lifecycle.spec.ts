import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import { useAudioToText } from '@/hooks/use-audio'

const mocks = vi.hoisted(() => ({ audioToText: vi.fn(), success: vi.fn(), state: undefined as ReturnType<typeof useAudioToText> | undefined }))
vi.mock('@/services/audio', () => ({ audioToText: mocks.audioToText, messageToAudio: vi.fn(), textToAudio: vi.fn() }))
vi.mock('@arco-design/web-vue', () => ({ Message: { success: mocks.success } }))
vi.mock('@/i18n', () => ({ i18n: { global: { t: (key: string) => key } } }))
const mountHook = () => mount(defineComponent({ setup() { mocks.state = useAudioToText(); return () => h('div') } }))

it('ignores late success and leaves a remounted instance clean', async () => {
  let finish!: (value: { data: { text: string } }) => void
  mocks.audioToText.mockReset().mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const wrapper = mountHook(), original = mocks.state!
  const pending = original.handleAudioToText(new Blob(['voice']))
  wrapper.unmount()
  const nextWrapper = mountHook(), next = mocks.state!
  finish({ data: { text: 'late transcript' } })
  await pending
  expect(original.loading.value).toBe(true)
  expect(original.text.value).toBe('')
  expect(next.loading.value).toBe(false)
  expect(next.text.value).toBe('')
  expect(mocks.success).not.toHaveBeenCalled()
  nextWrapper.unmount()
})
