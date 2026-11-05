import { ref } from 'vue'
import { uploadFile, uploadImage } from '@/services/upload-file'
import type { UploadFileResponse, UploadImageResponse } from '@/models/upload-file'

export const useUploadImage = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const image_url = ref<string>('')
  let uploadRequestId = 0

  // 2.定义上传图片处理器
  const handleUploadImage = async (image: File) => {
    const requestId = ++uploadRequestId
    try {
      loading.value = true
      const resp = await uploadImage(image)
      if (requestId === uploadRequestId) image_url.value = resp.data.image_url
      return resp
    } finally {
      if (requestId === uploadRequestId) loading.value = false
    }
  }

  return { loading, image_url, handleUploadImage }
}

export const useUploadFile = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const upload_file = ref<Record<string, any>>({})
  let uploadRequestId = 0

  // 2.定义上传文件处理器
  const handleUploadFile = async (file: File, signal?: AbortSignal): Promise<UploadFileResponse | undefined> => {
    const requestId = ++uploadRequestId
    try {
      loading.value = true
      const resp = await uploadFile(file, signal)
      if (requestId === uploadRequestId) upload_file.value = resp.data
      return resp
    } finally {
      if (requestId === uploadRequestId) loading.value = false
    }
  }

  return { loading, upload_file, handleUploadFile }
}
