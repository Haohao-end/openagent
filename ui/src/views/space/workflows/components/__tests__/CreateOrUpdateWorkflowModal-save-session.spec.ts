import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import CreateOrUpdateWorkflowModal from '../CreateOrUpdateWorkflowModal.vue'

const mocks = vi.hoisted(() => ({ save: vi.fn() }))
vi.mock('@/hooks/use-workflow', () => ({
  useCreateWorkflow: () => ({ loading: false, handleCreateWorkflow: mocks.save }),
  useGetWorkflow: () => ({ workflow: { value: {} }, loadWorkflow: vi.fn() }),
  useRegenerateIcon: () => ({ loading: false, handleRegenerateIcon: vi.fn() }),
  useGenerateIconPreview: () => ({ loading: false, handleGenerateIconPreview: vi.fn() }),
  useUpdateWorkflow: () => ({ loading: false, handleUpdateWorkflow: vi.fn() }),
}))
vi.mock('@/hooks/use-upload-file', () => ({ useUploadImage: () => ({ image_url: { value: '' }, handleUploadImage: vi.fn() }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

const FormStub = defineComponent({
  emits: ['submit'],
  methods: { resetFields: vi.fn() },
  template: '<form @submit.prevent="$emit(\'submit\', { errors: undefined })"><slot /></form>',
})
const ModalStub = defineComponent({
  emits: ['cancel'],
  template: '<div><button data-testid="cancel" @click="$emit(\'cancel\')"/><slot /></div>',
})

it('does not close a reopened workflow modal when an earlier save finishes', async () => {
  let finish!: () => void
  mocks.save.mockReset().mockReturnValueOnce(new Promise<void>((resolve) => { finish = resolve }))
  const callback = vi.fn()
  const wrapper = mount(CreateOrUpdateWorkflowModal, {
    props: { workflow_id: '', visible: false, callback },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-button': true, 'a-input': true, 'a-textarea': true, 'a-space': true, 'icon-close': true, IconUploadGenerator: true } },
  })

  await wrapper.setProps({ visible: true })
  await wrapper.get('form').trigger('submit')
  await wrapper.get('[data-testid="cancel"]').trigger('click')
  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true })
  finish()
  await flushPromises()
  expect(wrapper.emitted('update:visible')).toEqual([[false]])
  expect(callback).toHaveBeenCalledOnce()
  wrapper.unmount()
})
