import { ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  type CreateApiKeyRequest,
  type GetApiKeysWithPageResponse,
  type UpdateApiKeyRequest,
} from '@/models/api-key'
import {
  createApiKey,
  deleteApiKey,
  getApiKeysWithPage,
  updateApiKey,
  updateApiKeyIsActive,
} from '@/services/api-key'
import { Message, Modal } from '@arco-design/web-vue'
const parsePositiveIntegerQuery = (value: unknown, fallbackValue: number): number => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed <= 0) return fallbackValue
  return Math.floor(parsed)
}

export const useGetApiKeysWithPage = () => {
  // 1.定义hooks所需数据
  const route = useRoute()
  const loading = ref(false)
  const api_keys = ref<GetApiKeysWithPageResponse['data']['list']>([])
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref({ ...defaultPaginator })

  // 2.定义加载数据函数
  const loadApiKeys = async (init: boolean = false) => {
    if (!init && paginator.value.current_page > paginator.value.total_page) {
      return
    }

    try {
      loading.value = true
      const resp = await getApiKeysWithPage({
        current_page: parsePositiveIntegerQuery(route.query?.current_page, 1),
        page_size: parsePositiveIntegerQuery(route.query?.page_size, 20),
      })
      const data = resp.data

      paginator.value = data.paginator
      api_keys.value = data.list
    } finally {
      loading.value = false
    }
  }

  return { loading, api_keys, paginator, loadApiKeys }
}

export const useDeleteApiKey = () => {
  const handleDeleteApiKey = (api_key_id: string, callback?: () => void) => {
    Modal.warning({
      title: '要删除该API秘钥吗?',
      content:
        '删除秘钥后，无法使用该秘钥访问 LLMOps 个人空间中的所有 Agent，并且无法恢复，如果临时关闭请使用禁用功能。',
      hideCancel: false,
      onOk: async () => {
        try {
          // 1.点击确定后向API接口发起请求
          const resp = await deleteApiKey(api_key_id)
          Message.success(resp.message)
        } finally {
          // 2.调用callback函数指定回调功能
          callback && callback()
        }
      },
    })
  }

  return { handleDeleteApiKey }
}

export const useUpdateApiKey = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新处理器
  const handleUpdateApiKey = async (api_key_id: string, req: UpdateApiKeyRequest) => {
    try {
      loading.value = true
      const resp = await updateApiKey(api_key_id, req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateApiKey }
}

export const useUpdateApiKeyIsActive = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新处理器
  const handleUpdateApiKeyIsActive = async (
    api_key_id: string,
    is_active: boolean,
    callback?: () => void,
  ) => {
    try {
      loading.value = true
      const resp = await updateApiKeyIsActive(api_key_id, is_active)
      Message.success(resp.message)
    } finally {
      loading.value = false
      callback && callback()
    }
  }

  return { loading, handleUpdateApiKeyIsActive }
}

export const useCreateApiKey = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新处理器
  const handleCreateApiKey = async (req: CreateApiKeyRequest) => {
    try {
      loading.value = true
      const resp = await createApiKey(req)
      Message.success(resp.message || '创建API密钥成功')
      return String(resp.data?.api_key || '')
    } finally {
      loading.value = false
    }
  }

  return { loading, handleCreateApiKey }
}
