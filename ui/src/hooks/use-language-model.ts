import { ref } from 'vue'
import type { GetLanguageModelsResponse } from '@/models/language-model'
import { getLanguageModel, getLanguageModels } from '@/services/language-model'

export const useGetLanguageModels = () => {
  // 1.定义自定义hooks所需数据
  const loading = ref(false)
  let latestRequest = 0
  const language_models = ref<GetLanguageModelsResponse['data']>([])

  // 2.定义加载数据函数
  const loadLanguageModels = async () => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await getLanguageModels()
      if (requestId !== latestRequest) return false
      language_models.value = resp.data
      return true
    } catch (error: unknown) {
      if (requestId !== latestRequest) return false
      throw error
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, language_models, loadLanguageModels }
}

export const useGetLanguageModel = () => {
  // 1.定义自定义hooks所需数据
  const loading = ref(false)
  let latestRequest = 0
  const language_model = ref<Record<string, any>>({})

  // 2.定义加载数据函数
  const loadLanguageModel = async (provider_name: string, model_name: string) => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await getLanguageModel(provider_name, model_name)
      if (requestId !== latestRequest) return false
      language_model.value = resp.data
      return true
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, language_model, loadLanguageModel }
}
