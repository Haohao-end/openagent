import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import UpdateNameModal from '../UpdateNameModal.vue'

vi.mock('@/hooks/use-conversation', async () => {
  const { ref } = await import('vue')
  return { useUpdateConversationName: () => ({ loading: ref(false), handleUpdateConversationName: vi.fn() }) }
})

const FormStub = defineComponent({ setup: (_, { expose }) => { expose({ resetFields: () => {} }); return () => h('div') } })
const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible"><slot /></div>' })

it('clears the edited name when a reopened modal closes', async () => {
  const wrapper = mount(UpdateNameModal, {
    props: { visible: false, conversation_id: 'conversation-1' },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-input': true, 'a-button': true, 'a-space': true, 'icon-close': true } },
  })
  const state = (wrapper.vm as any).$.setupState

  await wrapper.setProps({ visible: true })
  state.form.name = 'First name'
  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true, conversation_id: 'conversation-2' })
  state.form.name = 'Second name'
  await wrapper.setProps({ visible: false })

  expect(state.form.name).toBe('')
  wrapper.unmount()
})
