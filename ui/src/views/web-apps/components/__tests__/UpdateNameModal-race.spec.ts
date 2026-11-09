import { defineComponent, h, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import UpdateNameModal from '../UpdateNameModal.vue'

const mocks = vi.hoisted(() => ({ update: vi.fn(), saved: vi.fn(), error: vi.fn() }))
vi.mock('@/hooks/use-conversation', async () => {
  const { ref } = await import('vue')
  return { useUpdateConversationName: () => ({ loading: ref(false), handleUpdateConversationName: mocks.update }) }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.error } }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

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
  mocks.saved.mockReset()
  const wrapper = mount(UpdateNameModal, {
    props: { visible: false, conversation_id: 'conversation-1', success_callback: mocks.saved },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-input': true, 'a-button': true, 'a-space': true, 'icon-close': true } },
  })

  await wrapper.setProps({ visible: true })
  const state = (wrapper.vm as any).$.setupState
  state.form.name = 'Old name'
  wrapper.findComponent(FormStub).vm.$emit('submit', { errors: undefined })
  await nextTick()
  if (action === 'reopen') {
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true, conversation_id: 'conversation-2' })
    state.form.name = 'New name'
  } else {
    wrapper.unmount()
  }
  resolve()
  await flushPromises()

  expect(mocks.update).toHaveBeenCalledWith('conversation-1', 'Old name')
  expect(mocks.saved).not.toHaveBeenCalled()
  expect(wrapper.emitted('update:visible')).toBeUndefined()
  if (action === 'reopen') wrapper.unmount()
})

it('reports a failed rename while the web-app modal is still active', async () => {
  mocks.error.mockReset()
  mocks.update.mockReset().mockRejectedValueOnce(new Error(''))
  mocks.saved.mockReset()
  const wrapper = mount(UpdateNameModal, {
    props: { visible: false, conversation_id: 'conversation-1', success_callback: mocks.saved },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-input': true, 'a-button': true, 'a-space': true, 'icon-close': true } },
  })
  await wrapper.setProps({ visible: true })
  const state = (wrapper.vm as any).$.setupState
  state.form.name = 'New name'

  await state.saveName({ errors: undefined }).catch(() => undefined)

  expect(mocks.error).toHaveBeenCalledWith('common.conversation.renameFailed')
  expect(mocks.saved).not.toHaveBeenCalled()
  expect(wrapper.emitted('update:visible')).toBeUndefined()
  wrapper.unmount()
})
