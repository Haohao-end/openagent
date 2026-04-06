import { ref } from 'vue'
import {
  assistantAgentChat,
  assistantAgentGenerateIntroduction,
  deleteAssistantAgentConversation,
  getAssistantAgentConversations,
  getAssistantAgentMessagesWithPage,
  stopAssistantAgentChat,
} from '@/services/assistant-agent'
import type {
  GetAssistantAgentConversationsResponse,
  GetAssistantAgentMessagesWithPageResponse,
} from '@/models/assistant-agent'
import { Message } from '@arco-design/web-vue'
export const useAssistantAgentChat = () => {
  // 1.定义自定义hooks所需数据
  const loading = ref(false)

  // 2.定义辅助Agent会话处理器
  const handleAssistantAgentChat = async (
    query: string,
    image_urls: string[] = [],
    conversation_id: string = '',
    onData: (event_response: Record<string, any>) => void,
  ) => {
    try {
      loading.value = true
      await assistantAgentChat(query, image_urls, conversation_id, onData)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleAssistantAgentChat }
}

export const useGenerateAssistantAgentIntroduction = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义个性化介绍生成处理器
  const handleGenerateAssistantAgentIntroduction = async (
    onData: (event_response: Record<string, any>) => void,
    signal?: AbortSignal,
  ) => {
    try {
      loading.value = true
      await assistantAgentGenerateIntroduction(onData, signal)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleGenerateAssistantAgentIntroduction }
}

export const useStopAssistantAgentChat = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义停止辅助Agent会话处理器
  const handleStopAssistantAgentChat = async (task_id: string) => {
    try {
      loading.value = true
      await stopAssistantAgentChat(task_id)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleStopAssistantAgentChat }
}

export const useGetAssistantAgentMessagesWithPage = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const messages = ref<GetAssistantAgentMessagesWithPageResponse['data']['list']>([])
  const created_at = ref(0)
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref({ ...defaultPaginator })

  // 2.定义加载数据函数
  const loadAssistantAgentMessages = async (
    init: boolean = false,
    conversation_id: string = '',
  ) => {
    // 2.1 判断是否是初始化，如果是则先初始化分页器
    if (init) {
      paginator.value = { ...defaultPaginator }
      created_at.value = 0
    } else if (paginator.value.current_page > paginator.value.total_page) {
      return
    }

    // 2.2 加载更多数据
    try {
      loading.value = true
      const resp = await getAssistantAgentMessagesWithPage({
        current_page: paginator.value.current_page,
        page_size: paginator.value.page_size,
        created_at: created_at.value,
        conversation_id,
      })
      const data = resp.data

      // 2.3 更新分页器
      paginator.value = data.paginator

      // 2.4 判断是否存在更多数据
      if (paginator.value.current_page <= paginator.value.total_page) {
        paginator.value.current_page += 1
      }

      // 2.5 追加或者覆盖数据
      if (init) {
        messages.value = data.list
      } else {
        messages.value.push(...data.list)
        created_at.value = data.list[0]?.created_at ?? 0
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, messages, paginator, loadAssistantAgentMessages }
}

export const useGetAssistantAgentConversations = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const conversations = ref<GetAssistantAgentConversationsResponse['data']>([])

  // 2.定义加载辅助Agent最近会话列表函数
  const loadAssistantAgentConversations = async (limit: number = 20) => {
    try {
      loading.value = true
      const resp = await getAssistantAgentConversations(limit)
      conversations.value = resp.data || []
    } finally {
      loading.value = false
    }
  }

  return { loading, conversations, loadAssistantAgentConversations }
}

export const useDeleteAssistantAgentConversation = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义删除调试会话处理器
  const handleDeleteAssistantAgentConversation = async () => {
    try {
      loading.value = true
      const resp = await deleteAssistantAgentConversation()
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleDeleteAssistantAgentConversation }
}
