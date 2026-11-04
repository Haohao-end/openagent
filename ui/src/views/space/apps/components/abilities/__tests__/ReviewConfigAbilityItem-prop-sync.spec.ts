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
