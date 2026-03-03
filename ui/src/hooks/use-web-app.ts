import { ref } from 'vue'
import { getWebApp, getWebAppConversations, stopWebAppChat, webAppChat } from '@/services/web-app'
import type { WebAppChatRequest } from '@/models/web-app'
import { Message } from '@arco-design/web-vue'
import { getErrorMessage } from '@/utils/error'

const runWithLoading = async <T>(
  loadingRef: { value: boolean },
  fallbackMessage: string,
  runner: () => Promise<T>,
): Promise<T> => {
  try {
    loadingRef.value = true
    return await runner()
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, fallbackMessage))
    throw error
  } finally {
    loadingRef.value = false
  }
}

export const useGetWebApp = () => {
  // 1.定义自定义hooks所需数据
  const loading = ref(false)
  const web_app = ref<Record<string, any>>({})

  // 2.定义加载数据处理器
  const loadWebApp = async (token: string) => {
    await runWithLoading(loading, '加载应用失败，请稍后重试', async () => {
      const resp = await getWebApp(token)
      web_app.value = resp.data
    })
  }

  return { loading, web_app, loadWebApp }
}

export const useWebAppChat = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义WebApp对话处理器
  const handleWebAppChat = async (
    token: string,
    req: WebAppChatRequest,
    onData: (event_response: Record<string, any>) => void,
  ) => {
    await runWithLoading(loading, '发送消息失败，请稍后重试', async () => {
      await webAppChat(token, req, onData)
    })
  }

  return { loading, handleWebAppChat }
}

export const useStopWebAppChat = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义停止WebApp对话处理器
  const handleStopWebAppChat = async (token: string, task_id: string) => {
    await runWithLoading(loading, '停止响应失败，请稍后重试', async () => {
      await stopWebAppChat(token, task_id)
    })
  }

  return { loading, handleStopWebAppChat }
}

export const useGetAppConversations = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const pinned_conversations = ref<Record<string, any>[]>([])
  const unpinned_conversations = ref<Record<string, any>[]>([])

  // 2.定义加载数据处理器
  const loadWebAppConversations = async (token: string) => {
    await runWithLoading(loading, '加载会话列表失败，请稍后重试', async () => {
      const [pinned_resp, unpinned_resp] = await Promise.all([
        getWebAppConversations(token, true),
        getWebAppConversations(token, false),
      ])

      pinned_conversations.value = pinned_resp.data
      unpinned_conversations.value = unpinned_resp.data
    })
  }

  return { loading, pinned_conversations, unpinned_conversations, loadWebAppConversations }
}
