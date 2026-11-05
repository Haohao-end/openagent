import { shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import ReviewConfigAbilityItem from '../ReviewConfigAbilityItem.vue'

const mocks = vi.hoisted(() => ({ update: vi.fn() }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  return { useUpdateDraftAppConfig: () => ({ loading: ref(false), handleUpdateDraftAppConfig: mocks.update }) }
})

it('preserves unsaved review settings when refreshed props arrive', async () => {
  const config = { enable: false, keywords: ['original'], inputs_config: { enable: false, preset_response: 'original' }, outputs_config: { enable: true } }
  const wrapper = shallowMount(ReviewConfigAbilityItem, { props: { app_id: 'app-1', review_config: config } })
  const state = (wrapper.vm.$ as any).setupState
  state.reviewConfigForm.keywords = 'unsaved keyword'
  await wrapper.setProps({ review_config: { ...config, keywords: ['server'] } })
  expect(state.reviewConfigForm.keywords).toBe('unsaved keyword')
  wrapper.unmount()
})

it('keeps reopened review settings open after an earlier save completes', async () => {
  let resolve!: () => void
  mocks.update.mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
  const wrapper = shallowMount(ReviewConfigAbilityItem, { props: { app_id: 'app-1', review_config: { enable: false, keywords: [], inputs_config: { enable: false, preset_response: '' }, outputs_config: { enable: false } } } })
  const state = (wrapper.vm.$ as any).setupState
  state.reviewConfigModalVisible = true
  const save = state.handleSubmitReviewConfig()
  state.handleCancelReviewConfigModal()
  state.reviewConfigModalVisible = true
  state.reviewConfigForm.keywords = 'new session'
  resolve()
  await save
  expect(state.reviewConfigModalVisible).toBe(true)
  expect(state.reviewConfigForm.keywords).toBe('new session')
  wrapper.unmount()
})

it('syncs the review quick toggle when its save starts outside the dialog', async () => {
  mocks.update.mockResolvedValueOnce(undefined)
  const wrapper = shallowMount(ReviewConfigAbilityItem, { props: { app_id: 'app-1', review_config: { enable: false, keywords: [], inputs_config: { enable: false, preset_response: '' }, outputs_config: { enable: false } } } })
  const state = (wrapper.vm.$ as any).setupState
  state.reviewConfigForm.enable = true
  await state.handleSubmitReviewConfig()
  expect(state.originReviewConfigForm.enable).toBe(true)
  wrapper.unmount()
})
