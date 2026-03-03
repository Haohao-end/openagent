import { ref } from 'vue'
import { uploadFile, uploadImage } from '@/services/upload-file'

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

  // 2.定义上传图片处理器
  const handleUploadFile = async (file: File) => {
    try {
      loading.value = true
      const resp = await uploadFile(file)
      upload_file.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, upload_file, handleUploadFile }
}
