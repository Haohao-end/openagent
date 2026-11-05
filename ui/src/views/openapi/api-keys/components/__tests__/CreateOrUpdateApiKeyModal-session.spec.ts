import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { expect, it, vi } from 'vitest'
import CreateOrUpdateApiKeyModal from '../CreateOrUpdateApiKeyModal.vue'
const mocks = vi.hoisted(() => ({ update: vi.fn(), create: vi.fn() }))
vi.mock('@/hooks/use-api-key', () => ({ useCreateApiKey: () => ({ loading: false, handleCreateApiKey: mocks.create }), useUpdateApiKey: () => ({ loading: false, handleUpdateApiKey: mocks.update }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
const form = defineComponent({ emits: ['submit'], template: `<form @submit.prevent="$emit('submit', { errors: undefined })"><slot /></form>` })
const modal = { props: ['visible'], template: '<div v-if="visible"><slot /></div>' }
it('ignores an API key save after its modal session changes', async () => {
  let resolve!: () => void
  mocks.update.mockReturnValueOnce(new Promise<void>((done) => { resolve = done }))
  const wrapper = mount(CreateOrUpdateApiKeyModal, { props: { visible: true, api_key_id: 'key-1', is_active: true, remark: 'first' }, global: { stubs: { 'a-modal': modal, 'a-form': form } } })
  await wrapper.get('form').trigger('submit')
  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true, api_key_id: 'key-2', remark: 'second' })
  resolve()
  await flushPromises()
  expect(wrapper.emitted('update:visible')).toBeUndefined()
})
