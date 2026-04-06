import { ref } from 'vue'
import {
  cancelPublish,
  copyApp,
  createApp,
  debugChat,
  deleteApp,
  deleteDebugConversation,
  fallbackHistoryToDraft,
  getApp,
  getAppsWithPage,
  getDebugConversationMessagesWithPage,
  getDebugConversationSummary,
  getDraftAppConfig,
  getPublishedConfig,
  getPublishHistoriesWithPage,
  getVersions,
  publish,
  promptCompareChat,
  regenerateWebAppToken,
  regenerateIcon,
  generateIconPreview,
  stopDebugChat,
  stopPromptCompareChat,
  updateApp,
  updateDebugConversationSummary,
  updateDraftAppConfig,
  shareAppToSquare,
  unshareAppFromSquare,
} from '@/services/app'
import { Message, Modal } from '@arco-design/web-vue'
import type {
  AppVersion,
  CreateAppRequest,
  GetAppsWithPageResponse,
  GetDebugConversationMessagesWithPageResponse,
  PromptCompareChatRequest,
  UpdateAppRequest,
  UpdateDraftAppConfigRequest,
} from '@/models/app'
import { useRouter } from 'vue-router'
import { getErrorMessage } from '@/utils/error'

export const useGetApp = () => {
  // 1.定义hooks所需的基础数据
  const loading = ref(false)
  const app = ref<Record<string, any>>({})

  // 2.定义加载数据所需的函数
  const loadApp = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await getApp(app_id)
      app.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, app, loadApp }
}

export const useGetAppsWithPage = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const apps = ref<GetAppsWithPageResponse['data']['list']>([])
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref({ ...defaultPaginator })

  // 2.定义加载数据函数
  const loadApps = async (init: boolean = false, search_word: string = '') => {
    // 2.1 判断是否是初始化，如果是的话则先初始化分页器
    if (init) {
      paginator.value = defaultPaginator
    } else if (paginator.value.current_page > paginator.value.total_page) {
      return
    }

    // 2.2 加载数据并更新
    try {
      // 2.3 将loading值改为true并调用api接口获取数据
      loading.value = true
      const resp = await getAppsWithPage({
        current_page: paginator.value.current_page,
        page_size: paginator.value.page_size,
        search_word: search_word,
      })
      const data = resp.data

      // 2.4 更新分页器
      paginator.value = data.paginator

      // 2.5 判断是否存在更多数据
      if (paginator.value.current_page <= paginator.value.total_page) {
        paginator.value.current_page += 1
      }

      // 2.6 追加或者是覆盖数据
      if (init) {
        apps.value = data.list
      } else {
        apps.value.push(...data.list)
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, apps, paginator, loadApps }
}

export const useCreateApp = () => {
  // 1.定义hooks所需数据
  const router = useRouter()
  const loading = ref(false)

  // 2.定义新增应用处理器
  const handleCreateApp = async (req: CreateAppRequest) => {
    try {
      loading.value = true
      const resp = await createApp(req)
      Message.success('新增Agent应用成功')
      await router.push({
        name: 'space-apps-detail',
        params: { app_id: resp.data.id },
      })
    } finally {
      loading.value = false
    }
  }

  return { loading, handleCreateApp }
}

export const useUpdateApp = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新数据处理器
  const handleUpdateApp = async (app_id: string, req: UpdateAppRequest) => {
    try {
      loading.value = true
      const resp = await updateApp(app_id, req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateApp }
}

export const useCopyApp = () => {
  // 1.定义hooks所需数据
  const router = useRouter()
  const loading = ref(false)

  // 2.定义拷贝应用副本处理器
  const handleCopyApp = async (app_id: string) => {
    try {
      // 2.1 修改loading并发起请求
      loading.value = true
      const resp = await copyApp(app_id)

      // 2.2 成功修改则进行提示并跳转页面
      Message.success('创建应用副本成功')
      await router.push({ name: 'space-apps-detail', params: { app_id: resp.data.id } })
    } finally {
      loading.value = false
    }
  }

  return { loading, handleCopyApp }
}

export const useDeleteApp = () => {
  const handleDeleteApp = async (app_id: string, callback?: () => void) => {
    Modal.warning({
      title: '要删除该应用吗?',
      content:
        '删除应用后，发布的WebApp、开放API以及关联的社交媒体平台均无法使用该Agent应用，如果需要暂停应用，可使用取消发布功能。',
      hideCancel: false,
      onOk: async () => {
        try {
          // 1.点击确定后向API接口发起请求
          const resp = await deleteApp(app_id)
          Message.success(resp.message)
        } finally {
          // 2.调用callback函数指定回调功能
          callback && callback()
        }
      },
    })
  }

  return { handleDeleteApp }
}

export const usePublish = () => {
  // 1.定义hooks所需的数据
  const loading = ref(false)

  // 2.定义更新发布处理器
  const handlePublish = async (app_id: string, share_to_square: boolean = true) => {
    try {
      loading.value = true
      await publish(app_id, share_to_square)
      if (share_to_square) {
        Message.success('应用已发布并共享到应用广场！')
      } else {
        Message.success('应用配置已更新！')
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, handlePublish }
}

export const useCancelPublish = () => {
  // 1.定义hooks所需的数据
  const loading = ref(false)

  // 2.定义取消发布处理器
  const handleCancelPublish = async (app_id: string, callback?: () => void) => {
    // 2.1打开弹窗提示
    Modal.warning({
      title: '要取消发布该Agent应用吗?',
      content:
        '取消发布后，应用将从应用广场移除，WebApp以及发布的社交平台均无法使用该Agent',
      hideCancel: false,
      onOk: async () => {
        try {
          // 2.2 点击确定后向API接口发起请求
          loading.value = true
          await cancelPublish(app_id)
          Message.success('应用已取消发布并从应用广场移除')
        } finally {
          // 2.3 调用callback函数指定回调功能
          loading.value = false
          callback && callback()
        }
      },
    })
  }

  return { loading, handleCancelPublish }
}

export const useGetPublishHistoriesWithPage = () => {
  // 1.定义hooks所需的数据
  const loading = ref(false)
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0,
  }
  const publishHistories = ref<Record<string, any>[]>([])
  const paginator = ref(defaultPaginator)

  // 2.定义加载数据函数
  const loadPublishHistories = async (app_id: string, init: boolean = false) => {
    try {
      // 2.1 判断是否为初始化，如果是则先初始化分页器
      if (init) {
        paginator.value = defaultPaginator
      } else if (paginator.value.current_page > paginator.value.total_page) {
        return
      }

      // 2.2 调用API接口获取数据
      loading.value = true
      const resp = await getPublishHistoriesWithPage(app_id, {
        current_page: paginator.value.current_page,
        page_size: paginator.value.page_size,
      })
      const data = resp.data

      // 2.3 更新分页器数据
      paginator.value = data.paginator

      // 2.4 是否存在更多数据
      if (paginator.value.current_page <= paginator.value.total_page) {
        paginator.value.current_page += 1
      }

      // 2.5 检测是追加数据还是覆盖数据
      if (init) {
        publishHistories.value = data.list
      } else {
        publishHistories.value.push(...data.list)
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, publishHistories, paginator, loadPublishHistories }
}

export const useFallbackHistoryToDraft = () => {
  // 1.定义hooks所需的数据
  const loading = ref(false)

  // 2.定义回退处理器
  const handleFallbackHistoryToDraft = async (
    app_id: string,
    app_config_version_id: string,
    callback?: () => void,
  ) => {
    try {
      loading.value = true
      const resp = await fallbackHistoryToDraft(app_id, app_config_version_id)
      Message.success(resp.message)
    } finally {
      loading.value = false
      callback && callback()
    }
  }

  return { loading, handleFallbackHistoryToDraft }
}

export const useGetDraftAppConfig = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const draftAppConfigForm = ref<Record<string, any>>({})

  // 2.定义加载数据函数
  const loadDraftAppConfig = async (app_id: string) => {
    try {
      // 2.1 修改loading状态并获取数据
      loading.value = true
      const resp = await getDraftAppConfig(app_id)
      const data = resp.data

      // 2.2 将数据同步到表单中
      draftAppConfigForm.value = {
        dialog_round: data.dialog_round,
        model_config: data.model_config,
        preset_prompt: data.preset_prompt,
        long_term_memory: data.long_term_memory,
        opening_statement: data.opening_statement,
        opening_questions: data.opening_questions,
        suggested_after_answer: data.suggested_after_answer,
        review_config: data.review_config,
        datasets: data.datasets,
        retrieval_config: data.retrieval_config,
        tools: data.tools,
        workflows: data.workflows,
        speech_to_text: data.speech_to_text,
        text_to_speech: data.text_to_speech,
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, draftAppConfigForm, loadDraftAppConfig }
}

export const useUpdateDraftAppConfig = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新草稿配置处理器
  const handleUpdateDraftAppConfig = async (
    app_id: string,
    draft_app_config: UpdateDraftAppConfigRequest,
  ) => {
    try {
      loading.value = true
      const resp = await updateDraftAppConfig(app_id, draft_app_config)
      Message.success(resp.message)
    } catch (error: unknown) {
      const msg = getErrorMessage(error, '更新应用草稿配置失败')
      Message.error(msg)
      throw error
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateDraftAppConfig }
}

export const useGetDebugConversationSummary = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const debug_conversation_summary = ref('')

  // 2.定义数据加载函数
  const loadDebugConversationSummary = async (app_id: string) => {
    try {
      // 2.1 调用API获取记忆
      loading.value = true
      const resp = await getDebugConversationSummary(app_id)
      const data = resp.data

      debug_conversation_summary.value = data.summary
    } finally {
      loading.value = false
    }
  }

  return { loading, debug_conversation_summary, loadDebugConversationSummary }
}

export const useUpdateDebugConversationSummary = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新处理器
  const handleUpdateDebugConversationSummary = async (app_id: string, summary: string) => {
    try {
      loading.value = true
      const resp = await updateDebugConversationSummary(app_id, summary)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateDebugConversationSummary }
}

export const useDeleteDebugConversation = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义删除调试会话处理器
  const handleDeleteDebugConversation = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await deleteDebugConversation(app_id)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleDeleteDebugConversation }
}

export const useGetDebugConversationMessagesWithPage = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const messages = ref<GetDebugConversationMessagesWithPageResponse['data']['list']>([])
  const created_at = ref(0)
  const defaultPaginator = {
    current_page: 1,
    page_size: 5,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref({ ...defaultPaginator })

  // 2.定义加载数据函数
  const loadDebugConversationMessages = async (
    app_id: string,
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
      const resp = await getDebugConversationMessagesWithPage(app_id, {
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

  return { loading, messages, paginator, loadDebugConversationMessages }
}

export const useDebugChat = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义调试会话处理器
  const handleDebugChat = async (
    app_id: string,
    query: string,
    image_urls: string[] = [],
    conversation_id: string = '',
    onData: (event_response: Record<string, any>) => void,
  ) => {
    try {
      loading.value = true
      await debugChat(app_id, query, image_urls, conversation_id, onData)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleDebugChat }
}

export const useStopDebugChat = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义停止调试会话处理器
  const handleStopDebugChat = async (app_id: string, task_id: string) => {
    try {
      loading.value = true
      await stopDebugChat(app_id, task_id)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleStopDebugChat }
}

export const usePromptCompareChat = () => {
  const loading = ref(false)

  const handlePromptCompareChat = async (
    app_id: string,
    req: PromptCompareChatRequest,
    onData: (event_response: Record<string, any>) => void,
  ) => {
    try {
      loading.value = true
      await promptCompareChat(app_id, req, onData)
    } finally {
      loading.value = false
    }
  }

  return { loading, handlePromptCompareChat }
}

export const useStopPromptCompareChat = () => {
  const loading = ref(false)

  const handleStopPromptCompareChat = async (app_id: string, task_id: string) => {
    try {
      loading.value = true
      await stopPromptCompareChat(app_id, task_id)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleStopPromptCompareChat }
}

export const useGetPublishedConfig = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const published_config = ref<Record<string, any>>({})

  // 2.定义加载数据函数
  const loadPublishedConfig = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await getPublishedConfig(app_id)
      published_config.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, published_config, loadPublishedConfig }
}

export const useRegenerateWebAppToken = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const token = ref<string>('')

  // 2.定义重生成WebAppToken函数
  const handleRegenerateWebAppToken = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await regenerateWebAppToken(app_id)
      Message.success('重新生成WebApp访问链接成功')
      token.value = resp.data.token
    } finally {
      loading.value = false
    }
  }

  return { loading, token, handleRegenerateWebAppToken }
}

export const useRegenerateIcon = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const icon = ref<string>('')

  // 2.定义重新生成图标函数
  const handleRegenerateIcon = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await regenerateIcon(app_id)
      icon.value = resp.data.icon
      return resp.data.icon
    } catch (error: unknown) {
      // 提取错误信息
      let errorMessage = '重新生成图标失败，请稍后重试'

      const msg = getErrorMessage(error, '')
      if (msg) {
        if (msg.includes('API_KEY')) {
          errorMessage = '图标生成服务暂时不可用，请联系管理员配置 API Key'
        } else if (msg.includes('所有服务均不可用')) {
          errorMessage = '图标生成服务暂时不可用，请稍后重试'
        } else {
          errorMessage = msg
        }
      }

      Message.error(errorMessage)
      throw error
    } finally {
      loading.value = false
    }
  }

  return { loading, icon, handleRegenerateIcon }
}

export const useGenerateIconPreview = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const icon = ref<string>('')

  // 2.定义生成图标预览函数
  const handleGenerateIconPreview = async (name: string, description: string) => {
    try {
      loading.value = true
      const resp = await generateIconPreview(name, description)
      icon.value = resp.data.icon
      return resp.data.icon
    } catch (error: unknown) {
      // 提取错误信息
      let errorMessage = '生成图标失败，请稍后重试'

      const msg = getErrorMessage(error, '')
      if (msg) {
        if (msg.includes('SILICONFLOW_API_KEY')) {
          errorMessage = '图标生成服务暂时不可用，请联系管理员配置 API Key'
        } else if (msg.includes('DASHSCOPE_API_KEY')) {
          errorMessage = '图标生成服务暂时不可用，请联系管理员配置 API Key'
        } else if (msg.includes('OPENAI_API_KEY')) {
          errorMessage = '图标生成服务暂时不可用，请联系管理员配置 API Key'
        } else if (msg.includes('所有服务均不可用')) {
          errorMessage = '图标生成服务暂时不可用，请稍后重试或手动上传图标'
        } else {
          errorMessage = msg
        }
      }

      Message.error(errorMessage)
      throw error
    } finally {
      loading.value = false
    }
  }

  return { loading, icon, handleGenerateIconPreview }
}

export const useShareAppToSquare = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义分享应用到广场处理器
  const handleShareAppToSquare = async (app_id: string, category: string, callback?: () => void) => {
    try {
      loading.value = true
      await shareAppToSquare(app_id, category)
      Message.success('应用已分享到应用广场')
    } finally {
      loading.value = false
      callback && callback()
    }
  }

  return { loading, handleShareAppToSquare }
}

export const useUnshareAppFromSquare = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义取消分享应用到广场处理器
  const handleUnshareAppFromSquare = async (app_id: string, callback?: () => void) => {
    Modal.warning({
      title: '要取消分享到广场吗?',
      content: '取消分享后，应用将从应用广场移除，但不会影响已发布的 WebApp 和 API',
      hideCancel: false,
      onOk: async () => {
        try {
          loading.value = true
          await unshareAppFromSquare(app_id)
          Message.success('应用已从应用广场移除')
        } finally {
          loading.value = false
          callback && callback()
        }
      },
    })
  }

  return { loading, handleUnshareAppFromSquare }
}

export const useGetVersions = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const versions = ref<AppVersion[]>([])

  // 2.定义加载版本数据函数
  const loadVersions = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await getVersions(app_id)
      versions.value = resp.data.list
    } finally {
      loading.value = false
    }
  }

  return { loading, versions, loadVersions }
}
