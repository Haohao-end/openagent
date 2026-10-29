import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ChatComposer from '../ChatComposer.vue'

describe('ChatComposer.vue', () => {
  it('shows a disabled transcribing action instead of stop while speech is being transcribed', async () => {
    const wrapper = mount(ChatComposer, {
      props: { modelValue: '', showVoiceButton: true, isRecording: true, audioToTextLoading: true },
    })

    expect(wrapper.find('[title="停止录音"]').exists()).toBe(false)
    const transcribingButton = wrapper.get('[title="正在转写"]')
    expect(transcribingButton.attributes('disabled')).toBeDefined()
    await transcribingButton.trigger('click')
    expect(wrapper.emitted('stop-record')).toBeUndefined()
  })

  it('allows stopping an active recording', async () => {
    const wrapper = mount(ChatComposer, {
      props: { modelValue: '', showVoiceButton: true, isRecording: true },
    })

    await wrapper.get('[title="停止录音"]').trigger('click')
    expect(wrapper.emitted('stop-record')).toEqual([[]])
  })

  it('renders upload button and emits upload when enabled', async () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
        showUploadButton: true,
      },
    })

    const uploadButton = wrapper.get('button[aria-label="上传图片"]')
    expect(uploadButton.attributes('disabled')).toBeUndefined()

    await uploadButton.trigger('click')

    expect(wrapper.emitted('upload')).toEqual([[]])
  })

  it('keeps upload button visible but disabled when upload is locked', async () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
        showUploadButton: true,
        uploadDisabled: true,
        uploadDisabledTitle: '当前公共应用预览链路暂不支持图片输入',
      },
    })

    const uploadButton = wrapper.get('button[aria-label="上传图片"]')
    expect(uploadButton.attributes('disabled')).toBeDefined()
    expect(uploadButton.attributes('title')).toBe('当前公共应用预览链路暂不支持图片输入')

    await uploadButton.trigger('click')

    expect(wrapper.emitted('upload')).toBeUndefined()
  })

  it('accepts dropped image files and emits file-change', async () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
        showUploadButton: true,
      },
    })

    const shell = wrapper.get('.chat-composer-shell')
    const file = new File(['image-bytes'], 'dragged.png', { type: 'image/png' })

    await shell.trigger('dragover', {
      dataTransfer: {
        files: [file],
      },
    })
    expect(shell.classes()).toContain('chat-composer-shell--drag-over')

    await shell.trigger('drop', {
      dataTransfer: {
        files: [file],
      },
    })

    const emitted = wrapper.emitted('file-change')
    expect(emitted).toHaveLength(1)
    expect((emitted?.[0]?.[0] as Event).target).toMatchObject({
      value: '',
    })
    expect(((emitted?.[0]?.[0] as Event).target as { files?: File[] }).files?.[0]).toBe(file)
  })

  it('does not render deep thinking toggle by default', () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
      },
    })

    expect(wrapper.find('[title="开启深度思考"]').exists()).toBe(false)
    expect(wrapper.find('[title="关闭深度思考"]').exists()).toBe(false)
  })

  it('renders deep thinking toggle and emits state changes when enabled', async () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
        showDeepThinkingToggle: true,
        deepThinkingEnabled: false,
      },
    })

    const toggle = wrapper.get('[title="开启深度思考"]')
    await toggle.trigger('click')

    expect(wrapper.emitted('update:deepThinkingEnabled')).toEqual([[true]])
  })

  it('reflects the active deep thinking state', () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
        showDeepThinkingToggle: true,
        deepThinkingEnabled: true,
      },
    })

    expect(wrapper.get('[title="关闭深度思考"]').attributes('aria-pressed')).toBe('true')
  })
})
