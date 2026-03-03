import { ref } from 'vue'
import { generateSuggestedQuestions, optimizePrompt } from '@/services/ai'

export const useGenerateSuggestedQuestions = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const suggested_questions = ref<string[]>([])

  // 2.定义加载数据函数
  const handleGenerateSuggestedQuestions = async (message_id: string) => {
    try {
      loading.value = true
      const resp = await generateSuggestedQuestions(message_id)
      suggested_questions.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, suggested_questions, handleGenerateSuggestedQuestions }
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
