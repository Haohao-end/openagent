import { defineComponent, h, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import CreateOrUpdateApiKeyModal from '../CreateOrUpdateApiKeyModal.vue'

const mocks = vi.hoisted(() => ({ update: vi.fn(), create: vi.fn(), showOnce: vi.fn(), error: vi.fn() }))
vi.mock('@/hooks/use-api-key', async () => {
  const { ref } = await import('vue')
  return {
    useUpdateApiKey: () => ({ loading: ref(false), handleUpdateApiKey: mocks.update }),
    useCreateApiKey: () => ({ loading: ref(false), handleCreateApiKey: mocks.create }),
  }
})
vi.mock('@arco-design/web-vue', () => ({
  Message: { success: vi.fn(), warning: vi.fn(), error: mocks.error },
  Modal: { info: mocks.showOnce },
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible"><slot /></div>' })
const FormStub = defineComponent({ emits: ['submit'], setup: () => () => h('div') })

const mountEditor = (props: { visible: boolean; api_key_id: string; remark?: string }, callback: () => void) => mount(CreateOrUpdateApiKeyModal, {
  props: { is_active: true, remark: 'first', callback, ...props },
  global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-switch': true, 'a-textarea': true, 'a-button': true, 'a-space': true, 'icon-safe': true, 'icon-close': true, 'icon-copy': true, 'icon-info-circle': true } },
})

it.each(['reopen', 'unmount'] as const)('ignores an update after the editor %s', async (action) => {
  let resolve!: () => void
  const callback = vi.fn()
  mocks.update.mockReset().mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
  const wrapper = mountEditor({ visible: false, api_key_id: 'key-1' }, callback)
  await wrapper.setProps({ visible: true })
  wrapper.findComponent(FormStub).vm.$emit('submit', { errors: undefined })
  await nextTick()
  if (action === 'reopen') {
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true, api_key_id: 'key-2', remark: 'second' })
  } else {
    wrapper.unmount()
  }
  resolve()
  await flushPromises()

  expect(mocks.update).toHaveBeenCalledWith('key-1', { is_active: true, remark: 'first' })
  expect(callback).not.toHaveBeenCalled()
  expect(wrapper.emitted('update:visible')).toBeUndefined()
  if (action === 'reopen') wrapper.unmount()
})

it('does not show a stale create key after another editor opens', async () => {
  let resolve!: (key: string) => void
  const callback = vi.fn()
  mocks.create.mockReset().mockReturnValueOnce(new Promise<string>((done) => { resolve = done }))
  mocks.showOnce.mockReset()
  const wrapper = mountEditor({ visible: false, api_key_id: '' }, callback)
  await wrapper.setProps({ visible: true })
  wrapper.findComponent(FormStub).vm.$emit('submit', { errors: undefined })
  await nextTick()
  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true, api_key_id: 'key-2' })
  resolve('new-secret')
  await flushPromises()

  expect(mocks.showOnce).not.toHaveBeenCalled()
  expect(callback).not.toHaveBeenCalled()
  expect(wrapper.emitted('update:visible')).toBeUndefined()
  wrapper.unmount()
})

it.each(['create', 'update'] as const)('reports an API key %s failure', async (action) => {
  const callback = vi.fn()
  mocks.error.mockReset()
  mocks.create.mockReset().mockRejectedValueOnce(new Error(''))
  mocks.update.mockReset().mockRejectedValueOnce(new Error(''))
  const wrapper = mountEditor({ visible: false, api_key_id: action === 'update' ? 'key-1' : '' }, callback)
  await wrapper.setProps({ visible: true })
  const state = (wrapper.vm as any).$.setupState

  await state.saveApiKey({ errors: undefined }).catch(() => undefined)

  expect(mocks.error).toHaveBeenCalledWith('openapi.apiKeys.saveFailed')
  expect(wrapper.emitted('update:visible')).toBeUndefined()
  expect(callback).not.toHaveBeenCalled()
  wrapper.unmount()
})
