import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ load: vi.fn().mockResolvedValue(undefined), save: vi.fn() }))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  return { useGetDebugConversationSummary: () => ({ debug_conversation_summary: ref('summary'), loadDebugConversationSummary: mocks.load }), useUpdateDebugConversationSummary: () => ({ loading: ref(false), handleUpdateDebugConversationSummary: mocks.save }) }
})
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
import PreviewDebugHeader from '../PreviewDebugHeader.vue'
const ButtonStub = defineComponent({ emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /><slot name="icon" /></button>' })
const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible" data-testid="summary-modal"><slot /></div>' })
it('keeps a reopened summary modal open after an earlier save completes', async () => {
  const wrapper = mount(PreviewDebugHeader, { props: { app_id: 'app-1', long_term_memory: { enable: true } }, global: { stubs: { 'a-button': ButtonStub, 'a-modal': ModalStub, 'a-textarea': true, 'icon-save': true, 'icon-close': true } } })
  let resolve!: () => void
  mocks.save.mockReset().mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
  const button = (text: string) => wrapper.findAll('button').find((item) => item.text().includes(text))!
  await button('appStudio.debug.longTermMemory').trigger('click')
  await flushPromises()
  await button('common.actions.save').trigger('click')
  await button('common.actions.cancel').trigger('click')
  await button('appStudio.debug.longTermMemory').trigger('click')
  await flushPromises()
  resolve(); await flushPromises()
  expect(wrapper.find('[data-testid="summary-modal"]').exists()).toBe(true)
  wrapper.unmount()
})
