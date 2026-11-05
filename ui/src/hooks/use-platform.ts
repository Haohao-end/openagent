import { ref } from 'vue'
import { getWechatConfig, updateWechatConfig } from '@/services/platform'
import type { UpdateWechatConfigRequest } from '@/models/platform'
import { Message } from '@arco-design/web-vue'
export const useGetWechatConfig = () => {
  // 1.定义自定义hooks所需数据
  const loading = ref(false)
  const wechat_config = ref<Record<string, any>>({})
  let latestRequest = 0

  // 2.定义加载数据处理器
  const loadWechatConfig = async (app_id: string) => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await getWechatConfig(app_id)
      if (requestId === latestRequest) wechat_config.value = resp.data
    } catch (error: unknown) {
      if (requestId === latestRequest) throw error
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, wechat_config, loadWechatConfig }
}

export const useUpdateWechatConfig = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新微信配置处理器
  const handleUpdateWechatConfig = async (app_id: string, req: UpdateWechatConfigRequest) => {
    try {
      loading.value = true
      const resp = await updateWechatConfig(app_id, req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateWechatConfig }
}
