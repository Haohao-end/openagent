import { getCurrentInstance, onUnmounted, type Ref } from 'vue'
import { i18n } from '@/i18n'
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
  let isUnmounted = false
  if (getCurrentInstance()) onUnmounted(() => { isUnmounted = true })

  const imageLimit = options.limit ?? CHAT_IMAGE_UPLOAD_LIMIT
  const limitMessage =
    options.limitMessage ?? (i18n.global.t('chat.composer.imageLimit', { count: imageLimit }) as string)
  const successMessage =
    options.successMessage ?? (i18n.global.t('chat.composer.uploadSuccess') as string)

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
    if (!canUploadMoreImages(options.imageUrls.value.length, imageLimit)) {
      options.onError(limitMessage)
      input.value = ''
      return
    }

    try {
      options.uploadFileLoading.value = true
      const resp = await options.uploadImage(selectedFile)
      if (isUnmounted) return
      const imageUrl = String(resp?.data?.image_url || '')
      if (!imageUrl) {
        options.onError(i18n.global.t('chat.composer.uploadFailed') as string)
        return
      }

      options.imageUrls.value.push(imageUrl)
      options.onSuccess(successMessage)
    } catch (error: unknown) {
      if (!isUnmounted) options.onError(getErrorMessage(error, i18n.global.t('chat.composer.uploadFailed') as string))
    } finally {
      if (!isUnmounted) {
        options.uploadFileLoading.value = false
        input.value = ''
      }
    }
  }

  return {
    triggerFileInput,
    handleFileChange,
  }
}
