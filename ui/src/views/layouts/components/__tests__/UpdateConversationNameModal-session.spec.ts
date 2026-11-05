import { defineComponent, h, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ update: vi.fn() }))
vi.mock('@/hooks/use-conversation', () => ({ useUpdateConversationName: () => ({ loading: { value: false }, handleUpdateConversationName: mocks.update }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
import UpdateConversationNameModal from '../UpdateConversationNameModal.vue'

const FormStub = defineComponent({ emits: ['submit'], setup(_, { expose }) { expose({ resetFields: () => {} }); return () => h('div') } })
const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible"><slot /></div>' })

it('ignores a save from an earlier conversation after the modal is reopened', async () => {
  const wrapper = mount(UpdateConversationNameModal, {
    props: { visible: false, conversation_id: 'conversation-1', conversation_name: 'Old name' },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-input': true, 'a-button': true, 'a-space': true, 'icon-close': true } },
  })
  let resolve!: () => void
  mocks.update.mockReset().mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
  await wrapper.setProps({ visible: true })
  wrapper.findComponent(FormStub).vm.$emit('submit', { errors: undefined })
  await nextTick()
  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true, conversation_id: 'conversation-2', conversation_name: 'New name' })
  resolve()
  await flushPromises()
  expect(wrapper.emitted('saved')).toBeUndefined()
  wrapper.unmount()
})
