import { shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import IconUploadGenerator from '../IconUploadGenerator.vue'

it('keeps the current icon when a replacement upload fails', async () => {
  const currentFile = { uid: 'current', name: 'Current icon', url: 'https://example.test/current.png' }
  const wrapper = shallowMount(IconUploadGenerator, {
    props: { name: 'Workflow', icon: currentFile.url, fileList: [currentFile],
      onUpload: vi.fn().mockRejectedValue(new Error('upload unavailable')), onGenerate: vi.fn() },
  })
  const state = (wrapper.vm as any).$.setupState
  const onError = vi.fn()

  await state.handleCustomRequest({
    fileItem: { file: new File(['icon'], 'replacement.png') }, onSuccess: vi.fn(), onError,
  })

  expect(onError).toHaveBeenCalledOnce()
  expect(state.localFileList).toEqual([currentFile])
  expect(wrapper.emitted('update:fileList')).toBeUndefined()
  wrapper.unmount()
})
