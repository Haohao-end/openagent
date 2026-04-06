<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthorize } from '@/hooks/use-oauth'
import { useCredentialStore } from '@/stores/credential'
import { isCredentialLoggedIn } from '@/utils/auth'
import { Message } from '@arco-design/web-vue'
import { getErrorMessage } from '@/utils/error'

// 1.定义页面所需的数据
const route = useRoute()
const router = useRouter()
const credentialStore = useCredentialStore()
const { authorization, handleAuthorize } = useAuthorize()
const authorizeError = ref('')
const providerName = computed(() => String(route.params?.provider_name ?? ''))
const OAUTH_ACTION_STORAGE_KEY = 'account_oauth_action'
const OAUTH_RESULT_STORAGE_KEY = 'account_oauth_result'
const LOGIN_CHALLENGE_STORAGE_KEY = 'pending_login_challenge'

const parseOAuthAction = () => {
  const raw = sessionStorage.getItem(OAUTH_ACTION_STORAGE_KEY)
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw)
    if (parsed?.intent !== 'bind') return null
    return {
      intent: 'bind' as const,
      provider: String(parsed.provider || ''),
    }
  } catch {
    return null
  }
}

const parseAuthorizeCode = () => {
  // 1.优先取路由query中的code
  const queryCode = route.query?.code
  if (queryCode) return String(queryCode)

  // 2.兼容从URL中直接读取code参数
  const searchCode = new URLSearchParams(window.location.search).get('code')
  if (searchCode) return searchCode

  // 3.兼容少数提供商把code放在hash中的场景
  const hash = window.location.hash
  if (hash.includes('code=')) {
    const hashParams = new URLSearchParams(hash.replace(/^#/, ''))
    const hashCode = hashParams.get('code')
    if (hashCode) return hashCode
  }

  return ''
}

const persistPendingLoginChallenge = (payload: {
  challenge_id?: string
  challenge_type?: string
  masked_email?: string
  risk_reason?: string
}) => {
  sessionStorage.setItem(
    LOGIN_CHALLENGE_STORAGE_KEY,
    JSON.stringify({
      ...payload,
      source: 'oauth',
      provider: providerName.value,
    }),
  )
}

onMounted(async () => {
  const oauthError = String(route.query?.error ?? '')
  if (oauthError) {
    authorizeError.value = `第三方授权失败: ${oauthError}`
    Message.error(authorizeError.value)
    return
  }

  const code = parseAuthorizeCode()
  if (!code) {
    authorizeError.value = '未获取到授权码(code)，请返回登录页重试'
    Message.error(authorizeError.value)
    return
  }

  try {
    const oauthAction = parseOAuthAction()
    const isBindAction =
      oauthAction?.intent === 'bind' &&
      oauthAction.provider === providerName.value &&
      isCredentialLoggedIn(credentialStore.credential)

    // 1.调用authorize接口进行登录或绑定
    await handleAuthorize(providerName.value, code, isBindAction ? 'bind' : 'login')
    const authorizationResult = authorization.value

    sessionStorage.removeItem(OAUTH_ACTION_STORAGE_KEY)

    if (isBindAction) {
      sessionStorage.setItem(
        OAUTH_RESULT_STORAGE_KEY,
        JSON.stringify({ action: 'bind', provider: providerName.value }),
      )
      await router.replace({
        path: '/home',
        query: { settings: 'account', tab: 'bindings', t: String(Date.now()) },
      })
      return
    }

    if (authorizationResult.challenge_required) {
      persistPendingLoginChallenge(authorizationResult)
      Message.warning('检测到新的登录环境，请完成邮箱验证码验证')
      await router.replace({ path: '/home', query: { login: '1', t: String(Date.now()) } })
      return
    }

    // 2.更新用户授权数据并跳转到首页
    sessionStorage.removeItem(LOGIN_CHALLENGE_STORAGE_KEY)
    credentialStore.update(authorizationResult)
    await router.replace({ path: '/home' })
  } catch (error: unknown) {
    sessionStorage.removeItem(OAUTH_ACTION_STORAGE_KEY)
    authorizeError.value = getErrorMessage(error, '第三方授权登录失败，请重试')
    Message.error(authorizeError.value)
  }
})
</script>

<template>
  <div class="w-full min-h-screen flex items-center justify-center bg-white">
    <div class="flex flex-col items-center gap-4">
      <a-spin v-if="!authorizeError" tip="第三方授权登录中..."></a-spin>
      <template v-else>
        <div class="text-sm text-red-500">{{ authorizeError }}</div>
        <a-button
          type="primary"
          @click="router.replace({ path: '/home', query: { login: '1', t: String(Date.now()) } })"
        >
          返回首页登录
        </a-button>
      </template>
    </div>
  </div>
</template>

<style scoped></style>
