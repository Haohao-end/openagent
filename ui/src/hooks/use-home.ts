import { ref } from 'vue'
import { getHomeIntent } from '@/services/home'
import type { HomeIntentData } from '@/models/home'

export const useGetHomeIntent = () => {
  const loading = ref(false)

  const loadHomeIntent = async (): Promise<HomeIntentData> => {
    try {
      loading.value = true
      const resp = await getHomeIntent()
      return resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, loadHomeIntent }
}
