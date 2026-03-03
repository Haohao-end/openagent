import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import {
  CHAT_IMAGE_UPLOAD_LIMIT,
  canUploadMoreImages,
  useChatImageUpload,
} from '@/hooks/use-chat-image-upload'

describe('useChatImageUpload', () => {
  it('checks image limit correctly', () => {
    expect(canUploadMoreImages(CHAT_IMAGE_UPLOAD_LIMIT - 1)).toBe(true)
    expect(canUploadMoreImages(CHAT_IMAGE_UPLOAD_LIMIT)).toBe(false)
  })

  it('shows error when trigger exceeds limit', () => {
    const onError = vi.fn()
    const onSuccess = vi.fn()
    const uploadImage = vi.fn()
    const click = vi.fn()

    const imageUrls = ref(Array.from({ length: CHAT_IMAGE_UPLOAD_LIMIT }, (_, idx) => `url-${idx}`))
    const uploadFileLoading = ref(false)
    const fileInput = ref({ click } as unknown as HTMLInputElement)

    const { triggerFileInput } = useChatImageUpload({
      imageUrls,
      uploadFileLoading,
      fileInput,
      uploadImage,
      onError,
      onSuccess,
    })

    const result = triggerFileInput()

    expect(result).toBe(false)
    expect(onError).toHaveBeenCalledWith('对话上传图片数量不能超过5张')
    expect(click).not.toHaveBeenCalled()
  })

  it('uploads selected file and appends image url', async () => {
    const onError = vi.fn()
    const onSuccess = vi.fn()
    const uploadImage = vi.fn().mockResolvedValue({
      data: {
        image_url: 'https://example.com/image.png',
      },
    })

    const imageUrls = ref<string[]>([])
    const uploadFileLoading = ref(false)
    const fileInput = ref<HTMLInputElement | null>(null)

    const { handleFileChange } = useChatImageUpload({
      imageUrls,
      uploadFileLoading,
      fileInput,
      uploadImage,
      onError,
      onSuccess,
    })

    const input = document.createElement('input')
    const file = new File(['image-bytes'], 'test.png', { type: 'image/png' })
    Object.defineProperty(input, 'files', {
      value: [file],
      configurable: true,
    })

    await handleFileChange({ target: input } as unknown as Event)

    expect(uploadImage).toHaveBeenCalledWith(file)
    expect(imageUrls.value).toEqual(['https://example.com/image.png'])
    expect(onSuccess).toHaveBeenCalledWith('上传图片成功')
    expect(onError).not.toHaveBeenCalled()
    expect(uploadFileLoading.value).toBe(false)
    expect(input.value).toBe('')
  })

  it('reports upload error and keeps image list unchanged', async () => {
    const onError = vi.fn()
    const onSuccess = vi.fn()
    const uploadImage = vi.fn().mockRejectedValue(new Error('网络异常'))

    const imageUrls = ref<string[]>([])
    const uploadFileLoading = ref(false)
    const fileInput = ref<HTMLInputElement | null>(null)

    const { handleFileChange } = useChatImageUpload({
      imageUrls,
      uploadFileLoading,
      fileInput,
      uploadImage,
      onError,
      onSuccess,
    })

    const input = document.createElement('input')
    const file = new File(['image-bytes'], 'test.png', { type: 'image/png' })
    Object.defineProperty(input, 'files', {
      value: [file],
      configurable: true,
    })

    await handleFileChange({ target: input } as unknown as Event)

    expect(imageUrls.value).toEqual([])
    expect(onSuccess).not.toHaveBeenCalled()
    expect(onError).toHaveBeenCalledWith('网络异常')
    expect(uploadFileLoading.value).toBe(false)
  })
})
