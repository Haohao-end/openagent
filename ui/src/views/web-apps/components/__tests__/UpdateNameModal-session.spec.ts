import { defineComponent, h, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ update: vi.fn(), saved: vi.fn() }))
vi.mock('@/hooks/use-conversation', () => ({ useUpdateConversationName: () => ({ loading: { value: false }, handleUpdateConversationName: mocks.update }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
import UpdateNameModal from '../UpdateNameModal.vue'

const FormStub = defineComponent({ emits: ['submit'], setup(_, { expose }) { expose({ resetFields: () => {} }); return () => h('div') } })
const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible"><slot /></div>' })

it('ignores a save from a prior web-app conversation after reopening', async () => {
  const wrapper = mount(UpdateNameModal, {
    props: { visible: false, conversation_id: 'conversation-1', success_callback: mocks.saved },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-input': true, 'a-button': true, 'a-space': true, 'icon-close': true } },
  })
  let resolve!: () => void
  mocks.update.mockReset().mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
  await wrapper.setProps({ visible: true })
  wrapper.findComponent(FormStub).vm.$emit('submit', { errors: undefined })
  await nextTick()
  await wrapper.setProps({ visible: false, conversation_id: '' })
  await wrapper.setProps({ visible: true, conversation_id: 'conversation-2' })
  resolve()
  await flushPromises()
  expect(mocks.saved).not.toHaveBeenCalled()
  wrapper.unmount()
})
