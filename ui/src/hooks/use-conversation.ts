import { ref } from 'vue'
import type {
  GetConversationMessagesWithPageResponse,
  GetRecentConversationsResponse,
} from '@/models/conversation'
import {
  deleteConversation,
  deleteMessage,
  getRecentConversations,
  getConversationMessages,
  getConversationName,
  updateConversationIsPinned,
  updateConversationName,
} from '@/services/conversation'
import { Message, Modal } from '@arco-design/web-vue'

export const useGetConversationMessagesWithPage = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const messages = ref<GetConversationMessagesWithPageResponse['data']['list']>([])
  const created_at = ref(0)
  const defaultPaginator = {
    current_page: 1,
    page_size: 5,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref({ ...defaultPaginator })

  // 2.定义加载数据函数
  const loadConversationMessagesWithPage = async (
    conversation_id: string,
    init: boolean = false,
  ) => {
    // 2.1 判断是否为初始化，如果是则先初始化分页器
    if (init) {
      paginator.value = { ...defaultPaginator }
      created_at.value = 0
    } else if (paginator.value.current_page > paginator.value.total_page) {
      return
    }

    // 2.2 加载更多数据
    try {
      loading.value = true
      const resp = await getConversationMessages(conversation_id, {
        current_page: paginator.value.current_page,
        page_size: paginator.value.page_size,
        created_at: created_at.value,
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

  return { loading, messages, paginator, loadConversationMessagesWithPage }
}

export const useDeleteConversation = () => {
  const handleDeleteConversation = (conversation_id: string, success_callback?: () => void) => {
    Modal.warning({
      title: '要删除该会话么?',
      content: '删除会话信息后，删除会话后，该会话下的所有聊天记录将被永远删除，无法找回。',
      hideCancel: false,
      onOk: async () => {
        // 1.点击确定后向API接口发起请求
        const resp = await deleteConversation(conversation_id)
        Message.success(resp.message)

        // 2.调用callback函数指定回调功能
        success_callback && success_callback()
      },
    })
  }

  return { handleDeleteConversation }
}

export const useDeleteMessage = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义删除消息处理器
  const handleDeleteMessage = async (conversation_id: string, message_id: string) => {
    try {
      loading.value = true
      await deleteMessage(conversation_id, message_id)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleDeleteMessage }
}

export const useGetConversationName = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const name = ref<string>('')

  // 2.定义加载数据处理器
  const loadConversationName = async (conversation_id: string) => {
    try {
      loading.value = true
      const resp = await getConversationName(conversation_id)
      name.value = resp.data.name
    } finally {
      loading.value = false
    }
  }

  return { loading, name, loadConversationName }
}

export const useUpdateConversationName = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新会话名字处理器
  const handleUpdateConversationName = async (conversation_id: string, name: string) => {
    try {
      loading.value = true
      const resp = await updateConversationName(conversation_id, name)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateConversationName }
}

export const useUpdateConversationIsPinned = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新置顶状态处理器
  const handleUpdateConversationIsPinned = async (
    conversation_id: string,
    is_pinned: boolean = false,
    success_callback?: () => void,
  ) => {
    try {
      loading.value = true
      const resp = await updateConversationIsPinned(conversation_id, is_pinned)
      Message.success(resp.message)
      success_callback && success_callback()
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateConversationIsPinned }
}

export const useGetRecentConversations = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const conversations = ref<GetRecentConversationsResponse['data']>([])

  // 2.定义加载最近会话列表处理器
  const loadRecentConversations = async (limit: number = 20) => {
    try {
      loading.value = true
      const resp = await getRecentConversations(limit)
      const data = resp.data || []
      // 直接赋值，不做任何转换
      conversations.value = data
      console.log('Loaded conversations:', conversations.value)
      if (conversations.value.length > 0) {
        console.log('First conversation:', conversations.value[0])
        console.log('human_message:', conversations.value[0].human_message)
        console.log('ai_message:', conversations.value[0].ai_message)
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, conversations, loadRecentConversations }
}
