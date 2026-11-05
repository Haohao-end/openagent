import { shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import TextToSpeechAbilityItem from '../TextToSpeechAbilitiItem.vue'

const mocks = vi.hoisted(() => ({ update: vi.fn() }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  return { useUpdateDraftAppConfig: () => ({ loading: ref(false), handleUpdateDraftAppConfig: mocks.update }) }
})

it('preserves unsaved voice settings when refreshed props arrive', async () => {
  const wrapper = shallowMount(TextToSpeechAbilityItem, { props: { app_id: 'app-1', text_to_speech: { enable: false, voice: 'original', auto_play: false } } })
  const state = (wrapper.vm.$ as any).setupState
  state.textToSpeechForm.voice = 'unsaved voice'
  await wrapper.setProps({ text_to_speech: { enable: true, voice: 'server voice', auto_play: true } })
  expect(state.textToSpeechForm).toMatchObject({ enable: false, voice: 'unsaved voice', auto_play: false })
  wrapper.unmount()
})

it('keeps reopened speech settings open after an earlier save completes', async () => {
  let resolve!: () => void
  mocks.update.mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
  const wrapper = shallowMount(TextToSpeechAbilityItem, { props: { app_id: 'app-1', text_to_speech: { enable: false, voice: 'original', auto_play: false } } })
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
