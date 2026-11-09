import { defineComponent, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import CreateOrUpdateWorkflowModal from '../CreateOrUpdateWorkflowModal.vue'

const mocks = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn(), load: vi.fn(), generate: vi.fn(), error: vi.fn() }))
vi.mock('@/hooks/use-workflow', () => ({
  useCreateWorkflow: () => ({ loading: false, handleCreateWorkflow: mocks.create }),
  useGetWorkflow: () => ({ workflow: ref({}), loading: ref(false), loadWorkflow: mocks.load }),
  useRegenerateIcon: () => ({ loading: false, handleRegenerateIcon: vi.fn() }),
  useGenerateIconPreview: () => ({ loading: false, handleGenerateIconPreview: mocks.generate }),
  useUpdateWorkflow: () => ({ loading: false, handleUpdateWorkflow: mocks.update }),
}))
vi.mock('@/hooks/use-upload-file', () => ({ useUploadImage: () => ({ image_url: ref(''), handleUploadImage: vi.fn() }) }))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.error } }))
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

it('does not close an edited modal after an earlier save finishes', async () => {
  let finish!: () => void
  mocks.update.mockReset().mockReturnValueOnce(new Promise<void>((resolve) => { finish = resolve }))
  const wrapper = mount(CreateOrUpdateWorkflowModal, {
    props: { workflow_id: 'workflow-1', visible: false },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-button': true, 'a-input': true, 'a-textarea': true, 'a-space': true, 'icon-close': true, IconUploadGenerator: true } },
  })

  await wrapper.setProps({ visible: true })
  await wrapper.get('form').trigger('submit')
  await wrapper.get('[data-testid="cancel"]').trigger('click')
  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true })
  finish()
  await flushPromises()

  expect(mocks.update).toHaveBeenCalledOnce()
  expect(wrapper.emitted('update:visible')).toEqual([[false]])
  wrapper.unmount()
})

it('does not run save side effects after the workflow modal unmounts', async () => {
  let finish!: () => void
  const callback = vi.fn()
  mocks.update.mockReset().mockReturnValueOnce(new Promise<void>((resolve) => { finish = resolve }))
  const success = mount(CreateOrUpdateWorkflowModal, {
    props: { workflow_id: 'workflow-1', visible: true, callback },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-button': true, 'a-input': true, 'a-textarea': true, 'a-space': true, 'icon-close': true, IconUploadGenerator: true } },
  })
  await success.get('form').trigger('submit')
  success.unmount()
  finish()
  await flushPromises()
  let fail!: (error: Error) => void
  mocks.error.mockReset()
  mocks.update.mockReturnValueOnce(new Promise<void>((_, reject) => { fail = reject }))
  const failure = mount(CreateOrUpdateWorkflowModal, {
    props: { workflow_id: 'workflow-1', visible: true },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-button': true, 'a-input': true, 'a-textarea': true, 'a-space': true, 'icon-close': true, IconUploadGenerator: true } },
  })
  await failure.get('form').trigger('submit')
  failure.unmount()
  fail(new Error('stale workflow failure'))
  await flushPromises()
  expect({ callbackCalls: callback.mock.calls.length, errorCalls: mocks.error.mock.calls.length }).toEqual({ callbackCalls: 0, errorCalls: 0 })
})

it('reports workflow detail failures and prevents saving an empty edit', async () => {
  mocks.load.mockReset().mockRejectedValueOnce(new Error('workflow details unavailable'))
  mocks.error.mockReset()
  mocks.update.mockReset()
  const wrapper = mount(CreateOrUpdateWorkflowModal, {
    props: { workflow_id: 'workflow-1', visible: false },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-button': true, 'a-input': true, 'a-textarea': true, 'a-space': true, 'icon-close': true, IconUploadGenerator: true } },
  })

  await wrapper.setProps({ visible: true })
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect({ errors: mocks.error.mock.calls.length, saves: mocks.update.mock.calls.length }).toEqual({ errors: 1, saves: 0 })
  wrapper.unmount()
})

it('passes a stale session check to an earlier workflow creation', async () => {
  let finish!: () => void
  mocks.create.mockReset().mockReturnValueOnce(new Promise<void>((resolve) => { finish = resolve }))
  const wrapper = mount(CreateOrUpdateWorkflowModal, {
    props: { workflow_id: '', visible: false },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-button': true, 'a-input': true, 'a-textarea': true, 'a-space': true, 'icon-close': true, IconUploadGenerator: true } },
  })

  await wrapper.setProps({ visible: true })
  await wrapper.get('form').trigger('submit')
  const shouldContinue = mocks.create.mock.calls[0]?.[1]
  await wrapper.get('[data-testid="cancel"]').trigger('click')
  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true })

  expect(shouldContinue?.()).toBe(false)
  finish()
  await flushPromises()
  wrapper.unmount()
})

it('does not report an icon generation failure from a previous modal session', async () => {
  let fail!: (error: Error) => void
  mocks.generate.mockReset().mockReturnValueOnce(new Promise<string>((_, reject) => { fail = reject }))
  mocks.error.mockReset()
  const wrapper = mount(CreateOrUpdateWorkflowModal, {
    props: { workflow_id: '', visible: false },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-button': true, 'a-input': true, 'a-textarea': true, 'a-space': true, 'icon-close': true, IconUploadGenerator: true } },
  })
  const vm = (wrapper.vm as any).$.setupState
  vm.form.name = 'New workflow'
  await wrapper.setProps({ visible: true })
  const generation = vm.handleGenerateIcon()
  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true })
  fail(new Error('stale generation failed'))
  await generation

  expect(mocks.error).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('does not report a save failure from a previous modal session', async () => {
  let fail!: (error: Error) => void
  mocks.load.mockReset().mockResolvedValue(undefined)
  mocks.update.mockReset().mockReturnValueOnce(new Promise<void>((_, reject) => { fail = reject }))
  mocks.error.mockReset()
  const wrapper = mount(CreateOrUpdateWorkflowModal, {
    props: { workflow_id: 'workflow-1', visible: false },
    global: { stubs: { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': true, 'a-button': true, 'a-input': true, 'a-textarea': true, 'a-space': true, 'icon-close': true, IconUploadGenerator: true } },
  })

  await wrapper.setProps({ visible: true })
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true })
  fail(new Error('stale save failed'))
  await flushPromises()

  expect(mocks.error).not.toHaveBeenCalled()
  wrapper.unmount()
})
