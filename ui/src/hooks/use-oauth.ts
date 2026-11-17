import { ref } from 'vue'
import { authorize, provider } from '@/services/oauth'
import { Message } from '@arco-design/web-vue'
import { type LoginAuthorizationData } from '@/models/auth'

export const useProvider = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const redirect_url = ref('')
  let latestRequest = 0

  // 2.定义获取提供者授权凭证地址处理器
  const handleProvider = async (provider_name: string) => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await provider(provider_name)
      if (requestId === latestRequest) {
        redirect_url.value = resp.data.redirect_url
      }
      return resp
    } finally {
      if (requestId === latestRequest) {
        loading.value = false
      }
    }
  }

  return { loading, redirect_url, handleProvider }
}

export const useAuthorize = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const authorization = ref<LoginAuthorizationData>({})
  let latestRequest = 0

  // 2.定义第三方授权认证处理器
  const handleAuthorize = async (
    provider_name: string,
    code: string,
    intent: 'login' | 'bind' = 'login',
  ) => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await authorize(provider_name, code, intent)
      if (requestId === latestRequest) {
        authorization.value = resp.data
        if (intent === 'bind') {
          Message.success('绑定成功，正在返回设置中心')
        } else if (!resp.data.challenge_required) {
          Message.success('登录成功，正在跳转')
        }
      }
      return resp
    } finally {
      if (requestId === latestRequest) {
        loading.value = false
      }
    }
  }

  return { loading, authorization, handleAuthorize }
}
