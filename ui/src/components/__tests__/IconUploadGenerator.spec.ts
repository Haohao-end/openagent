import { config, shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import IconUploadGenerator from '../IconUploadGenerator.vue'

config.global.stubs = {
  'a-space': { template: '<div class="arco-space"><slot /></div>' },
  'a-image': { props: ['src'], template: '<img :src="src" class="arco-image" />' },
  'a-button': { props: ['loading'], template: '<button :disabled="loading"><slot /><slot name="icon" /></button>' },
  'a-upload': { template: '<div class="arco-upload"><slot name="upload-button" /></div>' },
  'icon-delete': true,
  'icon-upload': true,
  'icon-robot': true,
  'icon-refresh': true,
}

it('keeps the current icon when a replacement upload fails and clears icon on removal', async () => {
  const currentFile = { uid: 'current', name: 'Current icon', url: 'https://example.test/current.png' }
  const wrapper = shallowMount(IconUploadGenerator, {
    props: {
      name: 'Workflow',
      icon: currentFile.url,
      fileList: [currentFile],
      onUpload: vi.fn().mockRejectedValue(new Error('upload unavailable')),
      onGenerate: vi.fn(),
    },
  })
  const state = (wrapper.vm as any).$.setupState
  const onError = vi.fn()

  await state.handleCustomRequest({
    fileItem: { file: new File(['icon'], 'replacement.png') },
    onSuccess: vi.fn(),
    onError,
  })

  expect(onError).toHaveBeenCalledOnce()
  expect(state.localFileList).toEqual([currentFile])
  expect(wrapper.emitted('update:fileList')).toBeUndefined()

  await state.handleBeforeRemove()
  expect(state.localIcon).toBe('')
  expect(state.localFileList).toEqual([])
  expect(wrapper.emitted('update:icon')).toEqual([['']])
  expect(wrapper.emitted('update:fileList')).toEqual([[[]]])
  wrapper.unmount()
})
