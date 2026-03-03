import { ref } from 'vue'
import {
  createApiToolProvider,
  deleteApiToolProvider,
  generateIconPreview,
  getApiTool,
  getApiToolProvider,
  getApiToolProvidersWithPage,
  regenerateIcon,
  updateApiToolProvider,
  validateOpenAPISchema,
} from '@/services/api-tool'
import { Message, Modal } from '@arco-design/web-vue'
import type { CreateApiToolProviderRequest, UpdateApiToolProviderRequest } from '@/models/api-tool'
import { getErrorMessage } from '@/utils/error'

export const useGetApiToolProvider = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const api_tool_provider = ref<Record<string, any>>({})

  // 2.定义加载数据函数
  const loadApiToolProvider = async (provider_id: string) => {
    try {
      loading.value = true
      const resp = await getApiToolProvider(provider_id)
      api_tool_provider.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, api_tool_provider, loadApiToolProvider }
}

export const useGetApiTool = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const api_tool = ref<Record<string, any>>({})

  // 2.定义加载函数
  const loadApiTool = async (provider_id: string, tool_name: string) => {
    try {
      loading.value = true
      const resp = await getApiTool(provider_id, tool_name)
      api_tool.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, api_tool, loadApiTool }
}

export const useGetApiToolProvidersWithPage = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const api_tool_providers = ref<Record<string, any>>([])
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref(defaultPaginator)

  // 2.定义加载数据函数
  const loadApiToolProviders = async (init: boolean = false, search_word: string = '') => {
    // 2.1 判断是否是初始化，如果是的话则先初始化分页器
    if (init) {
      paginator.value = defaultPaginator
      Object.assign(paginator, { ...defaultPaginator })
    } else if (paginator.value.current_page > paginator.value.total_page) {
      return
    }

    // 2.2 加载更多数据并更新数据状态
    try {
      // 2.3 调用接口获取响应数据
      loading.value = true
      const resp = await getApiToolProvidersWithPage(
        paginator.value.current_page,
        paginator.value.page_size,
        search_word,
      )
      const data = resp.data

      // 2.4 更新分页器
      paginator.value = data.paginator

      // 2.5 判断是否存在更多数据
      if (paginator.value.current_page <= paginator.value.total_page) {
        paginator.value.current_page += 1
      }

      // 2.6 追加或者是覆盖数据
      if (init) {
        api_tool_providers.value = data.list
      } else {
        api_tool_providers.value.push(...data.list)
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, api_tool_providers, paginator, loadApiToolProviders }
}

export const useDeleteApiToolProvider = () => {
  const handleDelete = (provider_id: string, success_callback?: () => void) => {
    Modal.warning({
      title: '删除这个工具?',
      content: '删除工具是不可逆的。AI应用将无法再访问您的工具',
      hideCancel: false,
      onOk: async () => {
        try {
          const resp = await deleteApiToolProvider(provider_id)
          Message.success(resp.message)
        } finally {
          success_callback && success_callback()
        }
      },
    })
  }

  return { handleDelete }
}

export const useUpdateApiToolProvider = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新api工具提供者处理器
  const handleUpdateApiToolProvider = async (
    provider_id: string,
    req: UpdateApiToolProviderRequest,
  ) => {
    try {
      loading.value = true
      const resp = await updateApiToolProvider(provider_id, req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateApiToolProvider }
}

export const useCreateApiToolProvider = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义创建api工具提供者处理器
  const handleCreateApiToolProvider = async (req: CreateApiToolProviderRequest) => {
    try {
      loading.value = true
      const resp = await createApiToolProvider(req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleCreateApiToolProvider }
}

export const useValidateOpenAPISchema = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义校验OpenAPI结构处理器
  const handleValidateOpenAPISchema = async (openapi_schema: string) => {
    try {
      loading.value = true
      const resp = await validateOpenAPISchema(openapi_schema)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleValidateOpenAPISchema }
}

export const useRegenerateIcon = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const icon = ref<string>('')

  // 2.定义重新生成图标函数
  const handleRegenerateIcon = async (provider_id: string) => {
    try {
      loading.value = true
      const resp = await regenerateIcon(provider_id)
      icon.value = resp.data.icon
      return resp.data.icon
    } catch (error: unknown) {
      let errorMessage = '重新生成图标失败，请稍后重试'
      const normalizedMessage = getErrorMessage(error, '')
      if (normalizedMessage.includes('API_KEY')) {
        errorMessage = '图标生成服务暂时不可用，请联系管理员配置 API Key'
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
      Message.error(getErrorMessage(error, '生成图标失败，请稍后重试或手动上传图标'))
      throw error
    } finally {
      loading.value = false
    }
  }

  return { loading, icon, handleGenerateIconPreview }
}
