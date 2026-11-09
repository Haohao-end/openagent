import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'
import AppModal from '../apps/components/CreateOrUpdateAppModal.vue'
import WorkflowModal from '../workflows/components/CreateOrUpdateWorkflowModal.vue'

const mocks = vi.hoisted(() => ({ app: null as any, workflow: null as any, loadApp: vi.fn(), loadWorkflow: vi.fn(), appRegenerateIcon: vi.fn(), workflowRegenerateIcon: vi.fn(), uploadImage: vi.fn(), uploadImageUrl: null as any }))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-upload-file', async () => {
  const { ref } = await import('vue')
  return { useUploadImage: () => {
    const image_url = ref('')
    mocks.uploadImageUrl = image_url
    return { image_url, handleUploadImage: mocks.uploadImage }
  } }
})
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  const noop = () => ({ loading: ref(false), handleCreateApp: vi.fn(), handleUpdateApp: vi.fn(), handleRegenerateIcon: vi.fn(), handleGenerateIconPreview: vi.fn() })
  return { useCreateApp: noop, useUpdateApp: noop, useRegenerateIcon: () => ({ loading: ref(false), handleRegenerateIcon: mocks.appRegenerateIcon }), useGenerateIconPreview: noop, useGetApp: () => ({ app: mocks.app, loadApp: mocks.loadApp }) }
})
vi.mock('@/hooks/use-workflow', async () => {
  const { ref } = await import('vue')
  const noop = () => ({ loading: ref(false), handleCreateWorkflow: vi.fn(), handleUpdateWorkflow: vi.fn(), handleRegenerateIcon: vi.fn(), handleGenerateIconPreview: vi.fn() })
  return { useCreateWorkflow: noop, useUpdateWorkflow: noop, useRegenerateIcon: () => ({ loading: ref(false), handleRegenerateIcon: mocks.workflowRegenerateIcon }), useGenerateIconPreview: noop, useGetWorkflow: () => ({ workflow: mocks.workflow, loadWorkflow: mocks.loadWorkflow }) }
})

const IconStub = defineComponent({ props: ['name', 'description', 'icon', 'onGenerate', 'onUpload'], template: '<span />' })
const FormStub = defineComponent({ template: '<form><slot /></form>', methods: { resetFields() {} } })
const SlotStub = { template: '<div><slot /></div>' }
const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible"><slot /></div>' })
const stubs = { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': SlotStub, IconUploadGenerator: IconStub }
const deferred = () => { let resolve!: () => void; const promise = new Promise<void>(done => { resolve = done }); return { promise, resolve } }
const deferredValue = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done }); return { promise, resolve } }

describe('create/update modal detail request races', () => {
  beforeEach(() => {
    mocks.app = ref({}); mocks.workflow = ref({}); mocks.loadApp.mockReset(); mocks.loadWorkflow.mockReset(); mocks.appRegenerateIcon.mockReset(); mocks.workflowRegenerateIcon.mockReset(); mocks.uploadImage.mockReset(); mocks.uploadImageUrl = null
  })

  it.each([
    ['app', AppModal, 'app_id', 'app-old', 'app', 'loadApp'],
    ['workflow', WorkflowModal, 'workflow_id', 'workflow-old', 'workflow', 'loadWorkflow'],
  ])('%s details do not fill a reopened create form', async (_kind, component, idProp, id, resourceKey, loadKey) => {
    const pending = deferred()
    const resource = resourceKey === 'app' ? mocks.app : mocks.workflow
    const load = loadKey === 'loadApp' ? mocks.loadApp : mocks.loadWorkflow
    load.mockImplementation(async () => { await pending.promise; resource.value = { name: 'Old resource', description: 'Old description', icon: '' } })
    const wrapper = mount(component as any, { props: { [idProp]: '', visible: false }, global: { stubs } })
    await wrapper.setProps({ [idProp]: id, visible: true })
    await flushPromises()
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ [idProp]: '', visible: true })
    pending.resolve()
    await flushPromises()

    expect(wrapper.findComponent(IconStub).props('name')).toBe('')
    wrapper.unmount()
  })

  it('clears fields when reopening a canceled workflow create form', async () => {
    const wrapper = mount(WorkflowModal as any, {
      props: { workflow_id: '', visible: false },
      global: { stubs },
    })
    await wrapper.setProps({ visible: true })
    const state = (wrapper.vm.$ as any).setupState
    state.form.name = 'First workflow'
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    state.form.name = 'Discarded workflow'
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })

    expect(state.form.name).toBe('')
    wrapper.unmount()
  })

  it('clears fields when reopening a canceled app create form', async () => {
    const wrapper = mount(AppModal as any, {
      props: { app_id: '', visible: false },
      global: { stubs },
    })
    await wrapper.setProps({ visible: true })
    const state = (wrapper.vm.$ as any).setupState
    state.form.name = 'First app'
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    state.form.name = 'Discarded app'
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })

    expect(state.form.name).toBe('')
    wrapper.unmount()
  })

  it('does not apply icon results from a previous app modal session', async () => {
    const pendingGeneration = deferredValue<string>()
    const pendingUpload = deferred()
    mocks.loadApp.mockImplementation(async (id: string) => {
      mocks.app.value = { name: id, description: id, icon: `icon-${id}` }
    })
    mocks.appRegenerateIcon.mockImplementation(async () => {
      await pendingGeneration.promise
      return 'icon-app-a-generated'
    })
    mocks.uploadImage.mockImplementation(async () => {
      await pendingUpload.promise
      mocks.uploadImageUrl.value = 'icon-app-a-uploaded'
    })

    const wrapper = mount(AppModal as any, {
      props: { app_id: '', visible: false },
      global: { stubs },
    })
    await wrapper.setProps({ app_id: 'app-a', visible: true })
    await flushPromises()

    const icon = wrapper.findComponent(IconStub)
    expect(icon.props('name')).toBe('app-a')
    const generation = (icon.props('onGenerate') as () => Promise<void>)()
    const upload = (icon.props('onUpload') as (file: File) => Promise<void>)(new File(['icon'], 'app-icon.png'))
    expect(mocks.appRegenerateIcon).toHaveBeenCalledWith('app-a')
    expect(mocks.uploadImage).toHaveBeenCalledTimes(1)

    await wrapper.setProps({ app_id: '', visible: false })
    await wrapper.setProps({ app_id: 'app-b', visible: true })
    await flushPromises()
    expect(wrapper.findComponent(IconStub).props('icon')).toBe('icon-app-b')

    pendingGeneration.resolve('done')
    await generation
    expect(wrapper.findComponent(IconStub).props('icon')).toBe('icon-app-b')
    pendingUpload.resolve()
    await upload

    expect(wrapper.findComponent(IconStub).props('icon')).toBe('icon-app-b')
    wrapper.unmount()
  })

  it('does not apply a generated workflow icon from a previous modal session', async () => {
    const pending = deferredValue<string>()
    mocks.loadWorkflow.mockImplementation(async (id: string) => {
      mocks.workflow.value = { name: id, description: id, icon: `icon-${id}`, tool_call_name: id }
    })
    mocks.workflowRegenerateIcon.mockImplementation(async () => {
      await pending.promise
      return 'icon-workflow-a-generated'
    })
    const pendingUpload = deferred()
    mocks.uploadImage.mockImplementation(async () => {
      await pendingUpload.promise
      mocks.uploadImageUrl.value = 'icon-workflow-a-uploaded'
    })

    const wrapper = mount(WorkflowModal as any, {
      props: { workflow_id: '', visible: false },
      global: { stubs },
    })
    await wrapper.setProps({ workflow_id: 'workflow-a', visible: true })
    await flushPromises()

    expect(wrapper.findComponent(IconStub).props('name')).toBe('workflow-a')
    const generateIcon = wrapper.findComponent(IconStub).props('onGenerate') as () => Promise<void>
    const generation = generateIcon()
    expect(mocks.workflowRegenerateIcon).toHaveBeenCalledWith('workflow-a', expect.any(Function))
    const uploadIcon = wrapper.findComponent(IconStub).props('onUpload') as (file: File) => Promise<void>
    const upload = uploadIcon(new File(['icon'], 'workflow-icon.png'))
    expect(mocks.uploadImage).toHaveBeenCalledTimes(1)
    await wrapper.setProps({ workflow_id: '', visible: false })
    await wrapper.setProps({ workflow_id: 'workflow-b', visible: true })
    await flushPromises()
    expect(wrapper.findComponent(IconStub).props('icon')).toBe('icon-workflow-b')

    pending.resolve('done')
    pendingUpload.resolve()
    await Promise.all([generation, upload])

    expect(wrapper.findComponent(IconStub).props('icon')).toBe('icon-workflow-b')
    wrapper.unmount()
  })
})
