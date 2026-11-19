import { ref } from 'vue'
import type { CreateFeedbackRequest } from '@/models/feedback'
import { createFeedback } from '@/services/feedback'

export const useFeedback = () => {
  const loading = ref(false)
  const submittedFeedbackId = ref<string | null>(null)
  let latestRequest = 0

  const clearFeedback = () => {
    latestRequest += 1
    loading.value = false
    submittedFeedbackId.value = null
  }

  const submitFeedback = async (app_id: string, req: CreateFeedbackRequest) => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await createFeedback(app_id, req)
      if (requestId !== latestRequest) return
      submittedFeedbackId.value = resp.data.id
      return resp.data
    } catch (error) {
      if (requestId !== latestRequest) return
      throw error
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, submittedFeedbackId, submitFeedback, clearFeedback }
}
