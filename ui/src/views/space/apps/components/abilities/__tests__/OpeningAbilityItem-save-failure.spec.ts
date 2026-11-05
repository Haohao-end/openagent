import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import OpeningAbilityItem from '../OpeningAbilityItem.vue'

const mocks = vi.hoisted(() => ({ save: vi.fn() }))
vi.mock('@/hooks/use-app', () => ({ useUpdateDraftAppConfig: () => ({ handleUpdateDraftAppConfig: mocks.save }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
const TextareaStub = { props: ['modelValue'], emits: ['update:modelValue', 'blur'], template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" @blur="$emit(\'blur\')" />' }
const SlotStub = { template: '<div><slot name="header"/><slot name="extra"/><slot/></div>' }

it('does not publish opening text when saving fails', async () => {
  mocks.save.mockRejectedValue(new Error('save failed'))
  const wrapper = mount(OpeningAbilityItem, { props: { app_id: 'app-1', opening_statement: 'Original statement', opening_questions: ['Original question'] }, global: { stubs: { 'a-collapse-item': SlotStub, 'a-textarea': TextareaStub, 'a-input': true, 'a-tooltip': SlotStub, 'a-button': true, 'icon-exclamation-circle': true, 'icon-delete': true }, config: { errorHandler: () => {} } } })
  await wrapper.get('textarea').setValue('Changed statement')
  await wrapper.get('textarea').trigger('blur')
  await flushPromises()
  expect(wrapper.emitted('update:opening_statement')).toBeUndefined()
  expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('Original statement')
  wrapper.unmount()
})
