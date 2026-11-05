import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import SuggestedAfterAnswerAbilityItem from '../SuggestedAfterAnswerAbilityItem.vue'

const mocks = vi.hoisted(() => ({ update: vi.fn() }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', () => ({ useUpdateDraftAppConfig: () => ({ handleUpdateDraftAppConfig: mocks.update }) }))

const CollapseStub = { template: '<div><slot /><slot name="header" /><slot name="extra" /></div>' }, DropdownStub = { emits: ['select'], template: '<div><slot /><slot name="content" /></div>' }

it('does not publish the enabled state when saving the toggle fails', async () => {
  mocks.update.mockRejectedValueOnce(new Error('save failed'))
  const wrapper = mount(SuggestedAfterAnswerAbilityItem, {
    props: { app_id: 'app-1', suggested_after_answer: { enable: false } },
    global: { stubs: { 'a-collapse-item': CollapseStub, 'a-dropdown': DropdownStub, 'a-button': true, 'a-doption': true, 'icon-down': true } },
  })
  wrapper.findComponent(DropdownStub).vm.$emit('select', 1)
  await flushPromises()
  expect(mocks.update).toHaveBeenCalledWith('app-1', { suggested_after_answer: { enable: true } })
  expect(wrapper.emitted('update:suggested_after_answer')).toBeUndefined()
  wrapper.unmount()
})
