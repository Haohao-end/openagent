import { ref } from 'vue'
import { generateSuggestedQuestions, optimizePrompt } from '@/services/ai'

export const useGenerateSuggestedQuestions = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const suggested_questions = ref<string[]>([])
  let requestGeneration = 0

  const clearSuggestedQuestions = () => {
    requestGeneration += 1
    suggested_questions.value = []
    loading.value = false
  }

  // 2.定义加载数据函数
  const handleGenerateSuggestedQuestions = async (message_id: string) => {
    const currentGeneration = ++requestGeneration
    try {
      loading.value = true
      const resp = await generateSuggestedQuestions(message_id)
      if (currentGeneration === requestGeneration) {
        suggested_questions.value = resp.data
      }
    } finally {
      if (currentGeneration === requestGeneration) {
        loading.value = false
      }
    }
  }

  return { loading, suggested_questions, handleGenerateSuggestedQuestions, clearSuggestedQuestions }
}

export const useOptimizePrompt = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const optimize_prompt = ref('')

  // 2.定义优化prompt处理器
  const handleOptimizePrompt = async (prompt: string) => {
    try {
      // 2.1 发起优化prompt请求，并将optimize_prompt先设置成空
      loading.value = true
      optimize_prompt.value = ''
      await optimizePrompt(prompt, (event_response) => {
        // 2.2 提取数据并更新optimize_prompt
        const data = event_response.data
        optimize_prompt.value += data?.optimize_prompt
      })
    } finally {
      loading.value = false
    }
  }

  return { loading, optimize_prompt, handleOptimizePrompt }
}
