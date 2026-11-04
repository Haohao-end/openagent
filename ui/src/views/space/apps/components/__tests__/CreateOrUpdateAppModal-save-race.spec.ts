import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import CreateOrUpdateAppModal from '@/views/space/apps/components/CreateOrUpdateAppModal.vue'
const { save } = vi.hoisted(() => ({ save: vi.fn() }))
vi.mock('@/hooks/use-app', () => ({
  useCreateApp: () => ({ loading: false, handleCreateApp: save }),
  useUpdateApp: () => ({ loading: false, handleUpdateApp: vi.fn() }),
  useGetApp: () => ({ app: { value: {} }, loadApp: vi.fn() }),
  useRegenerateIcon: () => ({ loading: false, handleRegenerateIcon: vi.fn() }),
  useGenerateIconPreview: () => ({ loading: false, handleGenerateIconPreview: vi.fn() }),
}))
vi.mock('@/hooks/use-upload-file', () => ({ useUploadImage: () => ({ image_url: { value: '' }, handleUploadImage: vi.fn() }) })); vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
it('keeps a reopened modal open when an earlier save finishes', async () => {
  let finish!: () => void; save.mockImplementation(() => new Promise<void>((resolve) => { finish = resolve }))
  const callback = vi.fn()
  const wrapper = shallowMount(CreateOrUpdateAppModal, {
    props: { app_id: '', visible: true, callback },
    global: { stubs: {
      IconUploadGenerator: true,
      'a-modal': { emits: ['cancel'], template: '<div><button data-testid="close" @click="$emit(\'cancel\')"/><slot/></div>' },
      'a-form': { emits: ['submit'], methods: { resetFields: vi.fn() }, template: '<form @submit.prevent="$emit(\'submit\', { errors: undefined })"><slot/></form>' },
    } },
  })
  await wrapper.get('form').trigger('submit')
  await wrapper.get('[data-testid="close"]').trigger('click')
  await wrapper.setProps({ visible: false })
  await wrapper.setProps({ visible: true })
  finish(); await flushPromises()
  expect(wrapper.emitted('update:visible')).toEqual([[false]])
  expect(callback).toHaveBeenCalledOnce(); wrapper.unmount()
})
