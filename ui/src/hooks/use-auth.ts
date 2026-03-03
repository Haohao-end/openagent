import { ref } from 'vue'
import { logout, passwordLogin } from '@/services/auth'
import { Message } from '@arco-design/web-vue'

export const useLogout = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义退出登录处理器
  const handleLogout = async () => {
    try {
      loading.value = true
      const resp = await logout()
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleLogout }
}

export const usePasswordLogin = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const authorization = ref<Record<string, any>>({})

  // 2.定义账号密码处理器
  const handlePasswordLogin = async (email: string, password: string) => {
    try {
      loading.value = true
      const resp = await passwordLogin(email, password)
      authorization.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, authorization, handlePasswordLogin }
}
