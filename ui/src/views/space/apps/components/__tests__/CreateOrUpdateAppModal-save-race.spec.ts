import { ref } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import CreateOrUpdateAppModal from '@/views/space/apps/components/CreateOrUpdateAppModal.vue'
const { save, update, error, load } = vi.hoisted(() => ({ save: vi.fn(), update: vi.fn(), error: vi.fn(), load: vi.fn() }))
const createLoading = ref(false)
const updateLoading = ref(false)
vi.mock('@/hooks/use-app', () => ({
  useCreateApp: () => ({ loading: createLoading, handleCreateApp: save }),
  useUpdateApp: () => ({ loading: updateLoading, handleUpdateApp: update }),
  useGetApp: () => ({ app: { value: {} }, loading: { value: false }, loadApp: load }),
  useRegenerateIcon: () => ({ loading: false, handleRegenerateIcon: vi.fn() }),
  useGenerateIconPreview: () => ({ loading: false, handleGenerateIconPreview: vi.fn() }),
}))
vi.mock('@arco-design/web-vue', () => ({ Message: { error, success: vi.fn() } }))
vi.mock('@/hooks/use-upload-file', () => ({ useUploadImage: () => ({ image_url: { value: '' }, handleUploadImage: vi.fn() }) })); vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

const defaultStubs = {
  IconUploadGenerator: true,
  'a-modal': { emits: ['cancel'], template: '<div><button data-testid="close" @click="$emit(\'cancel\')"/><slot/></div>' },
  'a-form': { emits: ['submit'], methods: { resetFields: vi.fn() }, template: '<form @submit.prevent="$emit(\'submit\', { errors: undefined })"><slot/></form>' },
  'a-button': { template: '<button type="button"><slot/></button>' },
  'a-form-item': { template: '<div><slot/></div>' },
  'a-input': { template: '<div class="a-input"><slot/></div>' },
  'a-textarea': { template: '<textarea />' },
  'icon-close': { template: '<span class="icon-close" />' },
}

it('keeps a reopened modal open when an earlier save finishes', async () => {
  let finish!: () => void; save.mockImplementation(() => new Promise<void>((resolve) => { finish = resolve }))
  const callback = vi.fn()
  const wrapper = shallowMount(CreateOrUpdateAppModal, {
    props: { app_id: '', visible: true, callback },
    global: { stubs: defaultStubs },
  })
  await wrapper.get('form').trigger('submit')
  await wrapper.get('[data-testid="close"]').trigger('click')
  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true })
  finish(); await flushPromises()
  expect(wrapper.emitted('update:visible')).toEqual([[false]])
  expect(callback).toHaveBeenCalledOnce(); wrapper.unmount()
})

it('reports an app save failure and keeps the form open', async () => {
  const unhandled: unknown[] = []
  const callback = vi.fn()
  save.mockReset().mockRejectedValueOnce(new Error('app save failed'))
  error.mockReset()
  const wrapper = shallowMount(CreateOrUpdateAppModal, {
    props: { app_id: '', visible: true, callback },
    global: {
      config: { errorHandler: (error) => unhandled.push(error) },
      stubs: defaultStubs,
    },
  })

  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect(error).toHaveBeenCalledWith('app save failed')
  expect(unhandled).toHaveLength(0)
  expect(wrapper.emitted('update:visible')).toBeUndefined()
  expect(callback).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('reports app detail failures and blocks an empty update', async () => {
  const unhandled: unknown[] = []
  load.mockReset().mockRejectedValueOnce(new Error('app details unavailable'))
  update.mockReset()
  error.mockReset()
  const wrapper = shallowMount(CreateOrUpdateAppModal, {
    props: { app_id: 'app-1', visible: false },
    global: {
      config: { errorHandler: (error) => unhandled.push(error) },
      stubs: defaultStubs,
    },
  })

  await wrapper.setProps({ visible: true })
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect(load).toHaveBeenCalledWith('app-1')
  expect(error).toHaveBeenCalledWith('app details unavailable')
  expect(update).not.toHaveBeenCalled()
  expect(unhandled).toHaveLength(0)
  wrapper.unmount()
})

it('blocks submission while an update or creation is already in progress', async () => {
  save.mockReset()
  update.mockReset()

  createLoading.value = true
  const createWrapper = shallowMount(CreateOrUpdateAppModal, {
    props: { app_id: '', visible: true },
    global: { stubs: defaultStubs },
  })
  await createWrapper.get('form').trigger('submit')
  await flushPromises()
  expect(save).not.toHaveBeenCalled()
  createLoading.value = false
  createWrapper.unmount()

  updateLoading.value = true
  const updateWrapper = shallowMount(CreateOrUpdateAppModal, {
    props: { app_id: 'app-1', visible: true },
    global: { stubs: defaultStubs },
  })
  await updateWrapper.get('form').trigger('submit')
  await flushPromises()
  expect(update).not.toHaveBeenCalled()
  updateLoading.value = false
  updateWrapper.unmount()
})
