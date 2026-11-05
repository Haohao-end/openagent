import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import OpeningAbilityItem from '../OpeningAbilityItem.vue'

const mocks = vi.hoisted(() => ({ save: vi.fn() }))
vi.mock('@/hooks/use-app', () => ({ useUpdateDraftAppConfig: () => ({ handleUpdateDraftAppConfig: mocks.save }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
const InputStub = defineComponent({
  props: ['modelValue'], emits: ['update:modelValue', 'blur'],
  template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" @blur="$emit(\'blur\')" />',
})
const SlotStub = { template: '<div><slot name="header"/><slot name="extra"/><slot/></div>' }

it('does not publish opening questions when saving fails', async () => {
  mocks.save.mockRejectedValue(new Error('save failed'))
  const wrapper = mount(OpeningAbilityItem, {
    props: { app_id: 'app-1', opening_statement: 'Opening', opening_questions: ['Original question'] },
    global: { stubs: { 'a-collapse-item': SlotStub, 'a-textarea': true, 'a-input': InputStub, 'a-tooltip': SlotStub, 'a-button': true, 'icon-exclamation-circle': true, 'icon-delete': true }, config: { errorHandler: () => {} } },
  })
  await wrapper.get('input').setValue('Changed question')
  await wrapper.get('input').trigger('blur')
  await flushPromises()
  expect(wrapper.emitted('update:opening_questions')).toBeUndefined()
  expect((wrapper.get('input').element as HTMLInputElement).value).toBe('Original question')
  wrapper.unmount()
})
