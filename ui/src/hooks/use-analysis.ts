import { ref } from 'vue'
import { getAppAnalysis } from '@/services/analysis'

export const useGetAppAnalysis = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const app_analysis = ref<Record<string, any>>({})
  let latestRequest = 0

  // 2.定义加载数据处理器
  const loadAppAnalysis = async (app_id: string) => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await getAppAnalysis(app_id)

      if (requestId !== latestRequest) return
      app_analysis.value = resp.data
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, app_analysis, loadAppAnalysis }
}
