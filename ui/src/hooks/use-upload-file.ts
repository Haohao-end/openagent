import { ref } from 'vue'
import { uploadFile, uploadImage } from '@/services/upload-file'
import type { UploadFileResponse, UploadImageResponse } from '@/models/upload-file'

export const useUploadImage = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const image_url = ref<string>('')

  // 2.定义上传图片处理器
  const handleUploadImage = async (image: File) => {
    try {
      loading.value = true
      const resp = await uploadImage(image)
      image_url.value = resp.data.image_url
      return resp
    } finally {
      loading.value = false
    }
  }

  return { loading, image_url, handleUploadImage }
}

export const useUploadFile = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const upload_file = ref<Record<string, any>>({})

  // 2.定义上传文件处理器
  const handleUploadFile = async (file: File): Promise<UploadFileResponse | undefined> => {
    try {
      loading.value = true
      console.log('[useUploadFile] Starting upload...')
      const resp = await uploadFile(file)
      console.log('[useUploadFile] Response received:', resp)
      console.log('[useUploadFile] Response data:', resp.data)
      upload_file.value = resp.data
      console.log('[useUploadFile] upload_file.value set to:', upload_file.value)
      return resp
    } catch (error) {
      console.error('[useUploadFile] Upload error:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  return { loading, upload_file, handleUploadFile }
}
