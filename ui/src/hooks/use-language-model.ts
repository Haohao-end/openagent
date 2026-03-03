import { ref } from 'vue'
import type { GetLanguageModelsResponse } from '@/models/language-model'
import { getLanguageModel, getLanguageModels } from '@/services/language-model'

export const useGetLanguageModels = () => {
  // 1.定义自定义hooks所需数据
  const loading = ref(false)
  const language_models = ref<GetLanguageModelsResponse['data']>([])

  // 2.定义加载数据函数
  const loadLanguageModels = async () => {
    try {
      loading.value = true
      const resp = await getLanguageModels()
      language_models.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, language_models, loadLanguageModels }
}

export const useGetLanguageModel = () => {
  // 1.定义自定义hooks所需数据
  const loading = ref(false)
  const language_model = ref<Record<string, any>>({})

  // 2.定义加载数据函数
  const loadLanguageModel = async (provider_name: string, model_name: string) => {
    try {
      loading.value = true
      const resp = await getLanguageModel(provider_name, model_name)

      language_model.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, language_model, loadLanguageModel }
}
