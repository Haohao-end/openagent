import { shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import TextToSpeechAbilityItem from '../TextToSpeechAbilitiItem.vue'

const mocks = vi.hoisted(() => ({ update: vi.fn() }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  return { useUpdateDraftAppConfig: () => ({ loading: ref(false), handleUpdateDraftAppConfig: mocks.update }) }
})

const defaultStubs = {
  'a-button': true,
  'a-collapse-item': true,
  'a-doption': true,
  'a-dropdown': true,
  'a-modal': true,
  'a-option': true,
  'a-select': true,
  'a-space': true,
  'a-switch': true,
  'icon-close': true,
  'icon-down': true,
  'icon-settings': true,
}

const mountAbilityItem = (props: { app_id: string; text_to_speech: Record<string, any> }) =>
  shallowMount(TextToSpeechAbilityItem, {
    props,
    global: { stubs: defaultStubs },
  })

it('preserves unsaved voice settings when refreshed props arrive', async () => {
  const wrapper = mountAbilityItem({ app_id: 'app-1', text_to_speech: { enable: false, voice: 'original', auto_play: false } })
  const state = (wrapper.vm.$ as any).setupState
  state.textToSpeechForm.voice = 'unsaved voice'
  await wrapper.setProps({ text_to_speech: { enable: true, voice: 'server voice', auto_play: true } })
  expect(state.textToSpeechForm).toMatchObject({ enable: false, voice: 'unsaved voice', auto_play: false })
  wrapper.unmount()
})

it('keeps reopened speech settings open after an earlier save completes', async () => {
  let resolve!: () => void
  mocks.update.mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
  const wrapper = mountAbilityItem({ app_id: 'app-1', text_to_speech: { enable: false, voice: 'original', auto_play: false } })
  const state = (wrapper.vm.$ as any).setupState
  state.textToSpeechModalVisible = true
  const save = state.handleSubmitTextToSpeech()
  state.handleCancelTextToSpeechModal()
  state.textToSpeechModalVisible = true
  state.textToSpeechForm.voice = 'new session'
  resolve()
  await save
  expect(state.textToSpeechModalVisible).toBe(true)
  expect(state.textToSpeechForm.voice).toBe('new session')
  wrapper.unmount()
})

it('keeps the dialog open and preserves form state when save fails', async () => {
  mocks.update.mockRejectedValueOnce(new Error('Update failed'))
  const wrapper = mountAbilityItem({ app_id: 'app-1', text_to_speech: { enable: false, voice: 'original', auto_play: false } })
  const state = (wrapper.vm.$ as any).setupState
  state.textToSpeechModalVisible = true
  state.textToSpeechForm.voice = 'failed voice'
  await state.handleSubmitTextToSpeech()
  expect(state.textToSpeechModalVisible).toBe(true)
  expect(state.textToSpeechForm.voice).toBe('failed voice')
  expect(state.originTextToSpeechForm.voice).toBe('original')
  wrapper.unmount()
})
