import { ref } from 'vue'
import { getHomeIntent } from '@/services/home'
import type { HomeIntentData } from '@/models/home'

export const useGetHomeIntent = () => {
  const loading = ref(false)
  let latestRequest = 0

  const loadHomeIntent = async (): Promise<HomeIntentData> => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await getHomeIntent()
      return resp.data
    } finally {
      if (requestId === latestRequest) {
        loading.value = false
      }
    }
  }

  return { loading, loadHomeIntent }
}
