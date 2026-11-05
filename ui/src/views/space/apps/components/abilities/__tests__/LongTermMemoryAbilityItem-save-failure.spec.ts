import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import LongTermMemoryAbilityItem from '../LongTermMemoryAbilityItem.vue'

const mocks = vi.hoisted(() => ({ update: vi.fn() }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', () => ({ useUpdateDraftAppConfig: () => ({ handleUpdateDraftAppConfig: mocks.update }) }))

const CollapseStub = { template: '<div><slot /><slot name="header" /><slot name="extra" /></div>' }, DropdownStub = { emits: ['select'], template: '<div><slot /><slot name="content" /></div>' }

it.each([['failed', false], ['successful', true]])('publishes the enabled state only after a %s save', async (_result, saveSucceeds) => {
  mocks.update.mockImplementationOnce(() => saveSucceeds ? Promise.resolve() : Promise.reject(new Error('save failed')))
  const wrapper = mount(LongTermMemoryAbilityItem, {
    props: { app_id: 'app-1', long_term_memory: { enable: false } },
    global: { stubs: { 'a-collapse-item': CollapseStub, 'a-dropdown': DropdownStub, 'a-button': true, 'a-doption': true, 'icon-down': true } },
  })

  wrapper.findComponent(DropdownStub).vm.$emit('select', 1)
  await flushPromises()

  expect(mocks.update).toHaveBeenCalledWith('app-1', { long_term_memory: { enable: true } })
  expect(wrapper.emitted('update:long_term_memory')).toEqual(saveSucceeds ? [[{ enable: true }]] : undefined)
  wrapper.unmount()
})
