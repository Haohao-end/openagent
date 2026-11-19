import { ref } from 'vue'
import {
  logout,
  passwordLogin,
  prepareRegister,
  resendLoginChallenge,
  verifyLoginChallenge,
  verifyRegister,
} from '@/services/auth'
import { Message } from '@arco-design/web-vue'
import { type LoginAuthorizationData } from '@/models/auth'

export const useLogout = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  let latestRequest = 0

  // 2.定义退出登录处理器
  const handleLogout = async () => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await logout()
      if (requestId === latestRequest) {
        Message.success(resp.message)
      }
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, handleLogout }
}

export const usePasswordLogin = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const authorization = ref<LoginAuthorizationData>({})
  let latestRequest = 0

  // 2.定义账号密码处理器
  const handlePasswordLogin = async (email: string, password: string) => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await passwordLogin(email, password)
      if (requestId === latestRequest) {
        authorization.value = resp.data
      }
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, authorization, handlePasswordLogin }
}

export const usePrepareRegister = () => {
  const loading = ref(false)
  let latestRequest = 0

  const handlePrepareRegister = async (email: string, password: string) => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await prepareRegister(email, password)
      return resp
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, handlePrepareRegister }
}

export const useVerifyRegister = () => {
  const loading = ref(false)
  const authorization = ref<LoginAuthorizationData>({})
  let latestRequest = 0

  const handleVerifyRegister = async (email: string, password: string, code: string) => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await verifyRegister(email, password, code)
      if (requestId === latestRequest) {
        authorization.value = resp.data
      }
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, authorization, handleVerifyRegister }
}

export const useVerifyLoginChallenge = () => {
  const loading = ref(false)
  const authorization = ref<LoginAuthorizationData>({})
  let latestRequest = 0

  const handleVerifyLoginChallenge = async (challenge_id: string, code: string) => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await verifyLoginChallenge(challenge_id, code)
      if (requestId === latestRequest) {
        authorization.value = resp.data
      }
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, authorization, handleVerifyLoginChallenge }
}

export const useResendLoginChallenge = () => {
  const loading = ref(false)
  let latestRequest = 0

  const handleResendLoginChallenge = async (challenge_id: string) => {
    const requestId = ++latestRequest
    try {
      loading.value = true
      const resp = await resendLoginChallenge(challenge_id)
      if (requestId === latestRequest) {
        Message.success(resp.message)
      }
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  return { loading, handleResendLoginChallenge }
}
