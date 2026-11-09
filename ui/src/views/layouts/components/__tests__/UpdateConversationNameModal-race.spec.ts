import { defineComponent, h, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import UpdateConversationNameModal from '../UpdateConversationNameModal.vue'

const mocks = vi.hoisted(() => ({ update: vi.fn() }))
vi.mock('@/hooks/use-conversation', async () => {
  const { ref } = await import('vue')
  return { useUpdateConversationName: () => ({ loading: ref(false), handleUpdateConversationName: mocks.update }) }
})

const FormStub = defineComponent({
  emits: ['submit'],
  setup(_, { expose }) {
    expose({ resetFields: () => {} })
    return () => h('div')
  },
})
const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible"><slot /></div>' })

it.each(['reopen', 'unmount'] as const)('ignores a save after the modal %s', async (action) => {
  let resolve!: () => void
  mocks.update.mockReset().mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
  const wrapper = mount(UpdateConversationNameModal, {
    props: { visible: false, conversation_id: 'conversation-1', conversation_name: 'Old name' },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-input': true, 'a-button': true, 'icon-close': true } },
  })

  await wrapper.setProps({ visible: true })
  wrapper.findComponent(FormStub).vm.$emit('submit', { errors: undefined })
  await nextTick()
  if (action === 'reopen') {
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true, conversation_id: 'conversation-2', conversation_name: 'New name' })
  } else {
    wrapper.unmount()
  }
  resolve()
  await flushPromises()

  expect(mocks.update).toHaveBeenCalledWith('conversation-1', 'Old name')
  expect(wrapper.emitted('saved')).toBeUndefined()
  expect(wrapper.emitted('update:visible')).toBeUndefined()
  if (action === 'reopen') wrapper.unmount()
})
