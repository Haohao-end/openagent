import { type Ref } from 'vue'
import { getErrorMessage } from '@/utils/error'

export const CHAT_IMAGE_UPLOAD_LIMIT = 5

export type UploadImageResponse = {
  data: {
    image_url: string
  }
}

type UseChatImageUploadOptions = {
  imageUrls: Ref<string[]>
  uploadFileLoading: Ref<boolean>
  fileInput: Ref<HTMLInputElement | null>
  uploadImage: (file: File) => Promise<UploadImageResponse>
  onError: (message: string) => void
  onSuccess: (message: string) => void
  limit?: number
  limitMessage?: string
  successMessage?: string
}

export const canUploadMoreImages = (
  currentCount: number,
  limit: number = CHAT_IMAGE_UPLOAD_LIMIT,
): boolean => {
  return currentCount < limit
}

export const useChatImageUpload = (options: UseChatImageUploadOptions) => {
  const imageLimit = options.limit ?? CHAT_IMAGE_UPLOAD_LIMIT
  const limitMessage = options.limitMessage ?? '对话上传图片数量不能超过5张'
  const successMessage = options.successMessage ?? '上传图片成功'

  const triggerFileInput = () => {
    if (!canUploadMoreImages(options.imageUrls.value.length, imageLimit)) {
      options.onError(limitMessage)
      return false
    }

    options.fileInput.value?.click()
    return true
  }

  const handleFileChange = async (event: Event) => {
    if (options.uploadFileLoading.value) return

    const input = event.target as HTMLInputElement
    const selectedFile = input.files?.[0]
    if (!selectedFile) return

    try {
      options.uploadFileLoading.value = true
      const resp = await options.uploadImage(selectedFile)
      const imageUrl = String(resp?.data?.image_url || '')
      if (!imageUrl) {
        options.onError('上传图片失败')
        return
      }

      options.imageUrls.value.push(imageUrl)
      options.onSuccess(successMessage)
    } catch (error: unknown) {
      options.onError(getErrorMessage(error, '上传图片失败'))
    } finally {
      options.uploadFileLoading.value = false
      input.value = ''
    }
  }

  return {
    triggerFileInput,
    handleFileChange,
  }
}
