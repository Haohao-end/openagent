import { ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getAppAnalysis } from '@/services/analysis'
import { getErrorMessage } from '@/utils/error'
import { i18n } from '@/i18n'

const t = (key: string) => i18n.global.t(key) as string

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
    } catch (error: unknown) {
      if (requestId === latestRequest) {
        Message.error(getErrorMessage(error, t('appStudio.analysis.loadFailed')))
      }
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, app_analysis, loadAppAnalysis }
}
