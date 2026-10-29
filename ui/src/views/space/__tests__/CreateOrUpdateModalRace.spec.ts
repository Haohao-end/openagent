import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'
import AppModal from '../apps/components/CreateOrUpdateAppModal.vue'
import WorkflowModal from '../workflows/components/CreateOrUpdateWorkflowModal.vue'

const mocks = vi.hoisted(() => ({ app: null as any, workflow: null as any, loadApp: vi.fn(), loadWorkflow: vi.fn() }))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-upload-file', async () => {
  const { ref } = await import('vue')
  return { useUploadImage: () => ({ image_url: ref(''), handleUploadImage: vi.fn() }) }
})
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  const noop = () => ({ loading: ref(false), handleCreateApp: vi.fn(), handleUpdateApp: vi.fn(), handleRegenerateIcon: vi.fn(), handleGenerateIconPreview: vi.fn() })
  return { useCreateApp: noop, useUpdateApp: noop, useRegenerateIcon: noop, useGenerateIconPreview: noop, useGetApp: () => ({ app: mocks.app, loadApp: mocks.loadApp }) }
})
vi.mock('@/hooks/use-workflow', async () => {
  const { ref } = await import('vue')
  const noop = () => ({ loading: ref(false), handleCreateWorkflow: vi.fn(), handleUpdateWorkflow: vi.fn(), handleRegenerateIcon: vi.fn(), handleGenerateIconPreview: vi.fn() })
  return { useCreateWorkflow: noop, useUpdateWorkflow: noop, useRegenerateIcon: noop, useGenerateIconPreview: noop, useGetWorkflow: () => ({ workflow: mocks.workflow, loadWorkflow: mocks.loadWorkflow }) }
})

const IconStub = defineComponent({ props: ['name', 'description'], template: '<span />' })
const FormStub = defineComponent({ template: '<form><slot /></form>', methods: { resetFields() {} } })
const SlotStub = { template: '<div><slot /></div>' }
const ModalStub = defineComponent({ props: ['visible'], template: '<div v-if="visible"><slot /></div>' })
const stubs = { 'a-modal': ModalStub, 'a-form': FormStub, 'a-form-item': SlotStub, IconUploadGenerator: IconStub }
const deferred = () => { let resolve!: () => void; const promise = new Promise<void>(done => { resolve = done }); return { promise, resolve } }

describe('create/update modal detail request races', () => {
  beforeEach(() => {
    mocks.app = ref({}); mocks.workflow = ref({}); mocks.loadApp.mockReset(); mocks.loadWorkflow.mockReset()
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
})
