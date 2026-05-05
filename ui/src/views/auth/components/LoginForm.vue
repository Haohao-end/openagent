<script setup lang="ts">
import IconOpenAgent from '@/components/icons/IconOpenAgent.vue'
import {
    usePasswordLogin,
    usePrepareRegister,
    useResendLoginChallenge,
    useVerifyLoginChallenge,
    useVerifyRegister,
} from '@/hooks/use-auth'
import { useProvider } from '@/hooks/use-oauth'
import { type LoginAuthorizationData } from '@/models/auth'
import { resetPassword, sendResetCode } from '@/services/auth'
import { useCredentialStore } from '@/stores/credential'
import { getErrorCode, getErrorMessage, getErrorReasonCode, getErrorResponseData } from '@/utils/error'
import { type ValidatedError, Message } from '@arco-design/web-vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

type AuthView = 'login' | 'register' | 'registerVerify' | 'challenge' | 'forgot'
type LoginChallengeSource = 'password' | 'oauth'
type SupportedOauthProvider = 'github' | 'google'
type LoginChallengeState = {
  challenge_id: string
  challenge_type: string
  masked_email: string
  risk_reason: string
  source: LoginChallengeSource
}

type RegisterFormState = {
  email: string
  password: string
  code: string
}

type PrepareRegisterResult =
  | {
      ok: true
      message: string
    }
  | {
      ok: false
      message: string
      reasonCode: string | null
      requestCode: string | null
      providers: SupportedOauthProvider[]
    }

const props = withDefaults(
  defineProps<{
    embedded?: boolean
    redirectAfterLogin?: boolean
  }>(),
  {
    embedded: false,
    redirectAfterLogin: true,
  },
)

const emits = defineEmits<{
  (event: 'success'): void
}>()

const STORAGE_KEY = 'login_credentials'
const LOGIN_CHALLENGE_STORAGE_KEY = 'pending_login_challenge'
const GENERIC_LOGIN_ERROR_MESSAGE = '账号不存在或者密码错误'
const LEGACY_ACCOUNT_NOT_FOUND_MESSAGE = '账号不存在'
const ACCOUNT_ALREADY_EXISTS_MESSAGE = '账号已存在，请直接登录'
const RESET_CODE_SENT_MESSAGE = '如果该邮箱已注册，验证码已发送，请查收'
const STRONG_PASSWORD_RULE_MESSAGE = '密码最少包含一个字母,一个数字,并且长度在8~16'
const REQUEST_VALIDATE_ERROR_CODE = 'validate_error'
const REQUEST_FAIL_ERROR_CODE = 'fail'
const REASON_INVALID_CREDENTIALS = 'INVALID_CREDENTIALS'
const REASON_ACCOUNT_EXISTS = 'ACCOUNT_EXISTS'
const REASON_OAUTH_ONLY_ACCOUNT = 'OAUTH_ONLY_ACCOUNT'
const REASON_RATE_LIMITED = 'RATE_LIMITED'
const REASON_SEND_PENDING = 'SEND_PENDING'
const STRONG_PASSWORD_REGEX = /^(?=.*[a-zA-Z])(?=.*\d).{8,16}$/
const OAUTH_PROVIDER_LABELS: Record<SupportedOauthProvider, string> = {
  github: 'GitHub',
  google: 'Google',
}
const AUTO_REGISTER_LOGIN_ERROR_MESSAGES = new Set([
  GENERIC_LOGIN_ERROR_MESSAGE,
  LEGACY_ACCOUNT_NOT_FOUND_MESSAGE,
])

const createEmptyChallenge = (): LoginChallengeState => ({
  challenge_id: '',
  challenge_type: '',
  masked_email: '',
  risk_reason: '',
  source: 'password',
})

const createEmptyRegisterForm = (): RegisterFormState => ({
  email: '',
  password: '',
  code: '',
})

const authView = ref<AuthView>('login')
const errorMessage = ref('')
const loginForm = ref({ email: '', password: '' })
const registerForm = ref<RegisterFormState>(createEmptyRegisterForm())
const rememberPassword = ref(true)
const oauthOnlyProviders = ref<SupportedOauthProvider[]>([])
const forgotStep = ref<1 | 2>(1)
const forgotForm = ref({
  email: '',
  code: '',
  new_password: '',
  confirm_password: '',
})
const loginChallenge = ref<LoginChallengeState>(createEmptyChallenge())
const challengeCode = ref('')
const sendingCode = ref(false)
const resetting = ref(false)
const countdown = ref(0)
const countdownTimer = ref<number>()
const challengeCountdown = ref(0)
const challengeTimer = ref<number>()
const registerCountdown = ref(0)
const registerTimer = ref<number>()
const credentialStore = useCredentialStore()
const router = useRouter()
const { loading: passwordLoginLoading, authorization, handlePasswordLogin } = usePasswordLogin()
const { loading: prepareRegisterLoading, handlePrepareRegister } = usePrepareRegister()
const {
  loading: verifyRegisterLoading,
  authorization: registerAuthorization,
  handleVerifyRegister,
} = useVerifyRegister()
const {
  loading: verifyLoginChallengeLoading,
  authorization: challengeAuthorization,
  handleVerifyLoginChallenge,
} = useVerifyLoginChallenge()
const { loading: resendLoginChallengeLoading, handleResendLoginChallenge } =
  useResendLoginChallenge()
const { loading: providerLoading, redirect_url, handleProvider } = useProvider()
const countdownText = computed(() => {
  return countdown.value > 0 ? `${countdown.value}秒后重发` : '发送验证码'
})
const challengeCountdownText = computed(() => {
  return challengeCountdown.value > 0 ? `${challengeCountdown.value}秒后重发` : '重发验证码'
})
const registerCountdownText = computed(() => {
  return registerCountdown.value > 0 ? `${registerCountdown.value}秒后重发` : '重发验证码'
})
const hasOauthOnlyProviders = computed(() => oauthOnlyProviders.value.length > 0)
const challengeDescription = computed(() => {
  if (loginChallenge.value.risk_reason === 'new_ip') {
    return `检测到本次登录来自新的 IP 环境。请输入发送到 ${loginChallenge.value.masked_email || '绑定邮箱'} 的验证码，确认是你本人操作。`
  }
  return `请输入发送到 ${loginChallenge.value.masked_email || '绑定邮箱'} 的验证码，完成本次登录验证。`
})
const registerEntryDescription = computed(() => {
  return `使用邮箱完成注册，我们会向 ${registerForm.value.email || '您的邮箱'} 发送验证码。`
})
const registerDescription = computed(() => {
  return `该邮箱尚未注册。请输入发送到 ${registerForm.value.email || '您的邮箱'} 的验证码，完成注册并登录。`
})

const getUserFriendlyErrorMessage = (error: unknown, fallback: string) => {
  const rawMessage = getErrorMessage(error, fallback).trim()
  if (!rawMessage) return fallback

  const normalizedMessage = rawMessage.toLowerCase()
  if (
    normalizedMessage.includes('traceback') ||
    normalizedMessage.includes('exception') ||
    normalizedMessage.includes('stack')
  ) {
    return fallback
  }

  if (
    normalizedMessage.includes('network') ||
    normalizedMessage.includes('failed to fetch') ||
    normalizedMessage.includes('timeout')
  ) {
    return '网络连接异常，请稍后重试'
  }

  return rawMessage
}

const normalizeOauthProviders = (providers: unknown): SupportedOauthProvider[] => {
  if (!Array.isArray(providers)) return []

  const normalizedProviders: SupportedOauthProvider[] = []
  providers.forEach((provider) => {
    const normalizedProvider = String(provider || '').trim().toLowerCase()
    if (normalizedProvider !== 'google' && normalizedProvider !== 'github') return
    if (normalizedProviders.includes(normalizedProvider)) return
    normalizedProviders.push(normalizedProvider)
  })

  return normalizedProviders
}

const extractOauthProvidersFromError = (error: unknown): SupportedOauthProvider[] => {
  const data = getErrorResponseData(error)
  if (!data) return []
  return normalizeOauthProviders(data.providers)
}

const clearOauthOnlyProviders = () => {
  oauthOnlyProviders.value = []
}

const shouldRenderOauthProvider = (provider: SupportedOauthProvider) => {
  return oauthOnlyProviders.value.includes(provider)
}

const persistPendingLoginChallenge = () => {
  sessionStorage.setItem(LOGIN_CHALLENGE_STORAGE_KEY, JSON.stringify(loginChallenge.value))
}

const clearPendingLoginChallenge = () => {
  sessionStorage.removeItem(LOGIN_CHALLENGE_STORAGE_KEY)
}

const startChallengeCountdown = () => {
  if (challengeTimer.value) {
    window.clearInterval(challengeTimer.value)
  }
  challengeCountdown.value = 60
  challengeTimer.value = window.setInterval(() => {
    challengeCountdown.value -= 1
    if (challengeCountdown.value <= 0) {
      if (challengeTimer.value) {
        window.clearInterval(challengeTimer.value)
        challengeTimer.value = undefined
      }
      challengeCountdown.value = 0
    }
  }, 1000)
}

const clearChallengeCountdown = () => {
  if (challengeTimer.value) {
    window.clearInterval(challengeTimer.value)
    challengeTimer.value = undefined
  }
  challengeCountdown.value = 0
}

const startRegisterCountdown = () => {
  if (registerTimer.value) {
    window.clearInterval(registerTimer.value)
  }
  registerCountdown.value = 60
  registerTimer.value = window.setInterval(() => {
    registerCountdown.value -= 1
    if (registerCountdown.value <= 0) {
      if (registerTimer.value) {
        window.clearInterval(registerTimer.value)
        registerTimer.value = undefined
      }
      registerCountdown.value = 0
    }
  }, 1000)
}

const clearRegisterCountdown = () => {
  if (registerTimer.value) {
    window.clearInterval(registerTimer.value)
    registerTimer.value = undefined
  }
  registerCountdown.value = 0
}

const applyLoginChallenge = (
  payload: LoginAuthorizationData,
  source: LoginChallengeSource = 'password',
) => {
  clearOauthOnlyProviders()
  loginChallenge.value = {
    challenge_id: String(payload.challenge_id || ''),
    challenge_type: String(payload.challenge_type || 'email_code'),
    masked_email: String(payload.masked_email || ''),
    risk_reason: String(payload.risk_reason || ''),
    source,
  }
  challengeCode.value = ''
  errorMessage.value = ''
  authView.value = 'challenge'
  persistPendingLoginChallenge()
  startChallengeCountdown()
}

const clearLoginChallenge = () => {
  loginChallenge.value = createEmptyChallenge()
  challengeCode.value = ''
  clearChallengeCountdown()
  clearPendingLoginChallenge()
}

const applyRegisterDraft = (email: string, password: string) => {
  registerForm.value = {
    email: email.trim(),
    password,
    code: '',
  }
}

const enterRegisterView = (
  email: string,
  password: string,
  options: {
    preserveError?: boolean
  } = {},
) => {
  applyRegisterDraft(email, password)
  clearRegisterCountdown()
  clearLoginChallenge()
  resetForgotForm()
  if (!options.preserveError) {
    errorMessage.value = ''
  }
  authView.value = 'register'
}

const applyRegisterVerification = (email: string, password: string) => {
  applyRegisterDraft(email, password)
  errorMessage.value = ''
  clearOauthOnlyProviders()
  authView.value = 'registerVerify'
  startRegisterCountdown()
}

const resetRegisterForm = () => {
  registerForm.value = createEmptyRegisterForm()
  clearRegisterCountdown()
}

const loadSavedCredentials = () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (!saved) return
    const { email, password } = JSON.parse(saved)
    loginForm.value.email = email || ''
    loginForm.value.password = password || ''
    rememberPassword.value = true
  } catch {
    localStorage.removeItem(STORAGE_KEY)
  }
}

const loadPendingLoginChallenge = () => {
  try {
    const saved = sessionStorage.getItem(LOGIN_CHALLENGE_STORAGE_KEY)
    if (!saved) return
    const parsed = JSON.parse(saved)
    if (!parsed?.challenge_id) {
      clearPendingLoginChallenge()
      return
    }
    loginChallenge.value = {
      challenge_id: String(parsed.challenge_id || ''),
      challenge_type: String(parsed.challenge_type || 'email_code'),
      masked_email: String(parsed.masked_email || ''),
      risk_reason: String(parsed.risk_reason || ''),
      source: parsed.source === 'oauth' ? 'oauth' : 'password',
    }
    authView.value = 'challenge'
    startChallengeCountdown()
  } catch {
    clearPendingLoginChallenge()
  }
}

const saveCredentials = (
  credentials: {
    email: string
    password: string
  } = loginForm.value,
) => {
  if (rememberPassword.value) {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        email: credentials.email,
        password: credentials.password,
      }),
    )
    return
  }
  localStorage.removeItem(STORAGE_KEY)
}

const handleRememberChange = (checked: boolean) => {
  if (!checked) localStorage.removeItem(STORAGE_KEY)
}

onMounted(() => {
  loadSavedCredentials()
  loadPendingLoginChallenge()
})

onBeforeUnmount(() => {
  if (countdownTimer.value) {
    window.clearInterval(countdownTimer.value)
  }
  clearChallengeCountdown()
  clearRegisterCountdown()
})

const clearCountdown = () => {
  if (countdownTimer.value) {
    window.clearInterval(countdownTimer.value)
    countdownTimer.value = undefined
  }
  countdown.value = 0
}

const resetForgotForm = () => {
  forgotStep.value = 1
  forgotForm.value.code = ''
  forgotForm.value.new_password = ''
  forgotForm.value.confirm_password = ''
  clearCountdown()
}

const openForgotPassword = () => {
  errorMessage.value = ''
  clearOauthOnlyProviders()
  authView.value = 'forgot'
  forgotForm.value.email = loginForm.value.email
  resetForgotForm()
}

const openRegister = () => {
  clearOauthOnlyProviders()
  enterRegisterView(loginForm.value.email, loginForm.value.password)
}

const backToLogin = () => {
  if (authView.value === 'register' || authView.value === 'registerVerify') {
    loginForm.value.email = registerForm.value.email
    loginForm.value.password = registerForm.value.password
  }
  errorMessage.value = ''
  clearOauthOnlyProviders()
  authView.value = 'login'
  resetForgotForm()
  resetRegisterForm()
  clearLoginChallenge()
}

const handleForgotBack = () => {
  if (forgotStep.value === 2) {
    forgotStep.value = 1
    return
  }
  backToLogin()
}

const validateEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

const handleSendCode = async () => {
  const email = forgotForm.value.email.trim()
  if (!email) {
    Message.error('请输入邮箱地址')
    return
  }

  if (!validateEmail(email)) {
    Message.error('请输入有效的邮箱地址')
    return
  }

  try {
    sendingCode.value = true
    const resp = await sendResetCode(email)
    Message.success(resp.message || RESET_CODE_SENT_MESSAGE)
    forgotStep.value = 2

    clearCountdown()
    countdown.value = 60
    countdownTimer.value = window.setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) {
        clearCountdown()
      }
    }, 1000)
  } catch (error: unknown) {
    Message.error(getUserFriendlyErrorMessage(error, '发送验证码失败，请稍后重试'))
  } finally {
    sendingCode.value = false
  }
}

const handleResendCode = async () => {
  if (countdown.value > 0) return
  await handleSendCode()
}

const finalizeLoginSuccess = async (credential: LoginAuthorizationData) => {
  clearPendingLoginChallenge()
  clearOauthOnlyProviders()
  credentialStore.update({
    access_token: String(credential.access_token || ''),
    expire_at: Number(credential.expire_at || 0),
  })

  if (props.redirectAfterLogin) {
    Message.success('登录成功，正在跳转')
    await router.replace({ path: '/home' })
    return
  }

  Message.success('登录成功')
  emits('success')
}

const handleVerifyChallenge = async () => {
  if (!loginChallenge.value.challenge_id) {
    errorMessage.value = '登录验证已失效，请重新登录'
    backToLogin()
    return
  }

  if (!challengeCode.value.trim()) {
    Message.error('请输入验证码')
    return
  }

  try {
    await handleVerifyLoginChallenge(loginChallenge.value.challenge_id, challengeCode.value.trim())
    const loginResult = challengeAuthorization.value
    if (loginChallenge.value.source === 'password') {
      saveCredentials()
    }
    clearLoginChallenge()
    await finalizeLoginSuccess(loginResult)
  } catch (error: unknown) {
    errorMessage.value = getUserFriendlyErrorMessage(error, '登录验证失败，请重试')
  }
}

const handleResendChallengeCode = async () => {
  if (challengeCountdown.value > 0 || !loginChallenge.value.challenge_id) return

  try {
    await handleResendLoginChallenge(loginChallenge.value.challenge_id)
    startChallengeCountdown()
  } catch (error: unknown) {
    errorMessage.value = getUserFriendlyErrorMessage(error, '验证码发送失败，请稍后重试')
  }
}

const prepareRegisterByEmailAndPassword = async (
  email: string,
  password: string,
): Promise<PrepareRegisterResult> => {
  try {
    clearOauthOnlyProviders()
    const resp = await handlePrepareRegister(email, password)
    applyRegisterVerification(email, password)
    const message = resp.message || '验证码已发送到您的邮箱,请查收'
    Message.success(message)
    return { ok: true, message }
  } catch (error: unknown) {
    const message = getUserFriendlyErrorMessage(error, '验证码发送失败，请稍后重试')
    const reasonCode = getErrorReasonCode(error)
    const requestCode = getErrorCode(error)
    const providers =
      reasonCode === REASON_OAUTH_ONLY_ACCOUNT ? extractOauthProvidersFromError(error) : []
    if (reasonCode === REASON_OAUTH_ONLY_ACCOUNT) {
      oauthOnlyProviders.value = providers
    } else {
      clearOauthOnlyProviders()
    }
    errorMessage.value = message
    return { ok: false, message, reasonCode, requestCode, providers }
  }
}

const handlePrepareRegisterAction = async (): Promise<PrepareRegisterResult> => {
  return await prepareRegisterByEmailAndPassword(
    loginForm.value.email.trim(),
    loginForm.value.password,
  )
}

const handleStartRegister = async () => {
  const email = registerForm.value.email.trim()
  const password = registerForm.value.password

  if (!email) {
    Message.error('请输入邮箱地址')
    return
  }

  if (!validateEmail(email)) {
    Message.error('请输入有效的邮箱地址')
    return
  }

  if (!password) {
    Message.error('请输入注册密码')
    return
  }

  if (!STRONG_PASSWORD_REGEX.test(password)) {
    Message.error(STRONG_PASSWORD_RULE_MESSAGE)
    return
  }

  errorMessage.value = ''
  const result = await prepareRegisterByEmailAndPassword(email, password)
  if (result.ok) return

  if (result.reasonCode === REASON_ACCOUNT_EXISTS) {
    loginForm.value.email = email
    loginForm.value.password = ''
    authView.value = 'login'
    errorMessage.value = ACCOUNT_ALREADY_EXISTS_MESSAGE
  }
}

const handleResendRegisterCode = async () => {
  if (registerCountdown.value > 0) return

  try {
    const resp = await handlePrepareRegister(registerForm.value.email.trim(), registerForm.value.password)
    startRegisterCountdown()
    Message.success(resp.message || '验证码已发送到您的邮箱,请查收')
  } catch (error: unknown) {
    Message.error(getUserFriendlyErrorMessage(error, '验证码发送失败，请稍后重试'))
  }
}

const handleVerifyRegisterAction = async () => {
  if (!registerForm.value.code.trim()) {
    Message.error('请输入验证码')
    return
  }

  try {
    await handleVerifyRegister(
      registerForm.value.email.trim(),
      registerForm.value.password,
      registerForm.value.code.trim(),
    )
    saveCredentials({
      email: registerForm.value.email.trim(),
      password: registerForm.value.password,
    })
    const loginResult = registerAuthorization.value
    resetRegisterForm()
    await finalizeLoginSuccess(loginResult)
  } catch (error: unknown) {
    errorMessage.value = getUserFriendlyErrorMessage(error, '注册失败，请稍后重试')
  }
}

const handleResetPassword = async () => {
  if (!forgotForm.value.code) {
    Message.error('请输入验证码')
    return
  }

  if (!forgotForm.value.new_password) {
    Message.error('请输入新密码')
    return
  }

  if (forgotForm.value.new_password !== forgotForm.value.confirm_password) {
    Message.error('两次输入的密码不一致')
    return
  }

  if (!STRONG_PASSWORD_REGEX.test(forgotForm.value.new_password)) {
    Message.error(STRONG_PASSWORD_RULE_MESSAGE)
    return
  }

  try {
    resetting.value = true
    await resetPassword(
      forgotForm.value.email.trim(),
      forgotForm.value.code.trim(),
      forgotForm.value.new_password,
    )
    Message.success('密码重置成功,请使用新密码登录')
    loginForm.value.email = forgotForm.value.email.trim()
    loginForm.value.password = ''
    backToLogin()
  } catch (error: unknown) {
    Message.error(getUserFriendlyErrorMessage(error, '密码重置失败，请稍后重试'))
  } finally {
    resetting.value = false
  }
}

const githubLogin = async () => {
  await handleProvider('github')
  window.location.href = redirect_url.value
}

const googleLogin = async () => {
  await handleProvider('google')
  window.location.href = redirect_url.value
}

const handleSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  if (errors) return

  try {
    errorMessage.value = ''
    clearOauthOnlyProviders()
    await handlePasswordLogin(loginForm.value.email, loginForm.value.password)
    const loginResult = authorization.value

    if (loginResult.challenge_required) {
      applyLoginChallenge(loginResult, 'password')
      Message.warning('检测到新的登录环境，请完成邮箱验证码验证')
      return
    }

    saveCredentials()
    await finalizeLoginSuccess(loginResult)
  } catch (error: unknown) {
    const message = getUserFriendlyErrorMessage(error, '登录失败，请检查邮箱和密码后重试')
    const reasonCode = getErrorReasonCode(error)
    const shouldAutoRegister =
      reasonCode === REASON_INVALID_CREDENTIALS ||
      (reasonCode === null && AUTO_REGISTER_LOGIN_ERROR_MESSAGES.has(message))

    if (shouldAutoRegister) {
      const result = await handlePrepareRegisterAction()
      if (result.ok) {
        return
      }

      if (result.reasonCode === REASON_ACCOUNT_EXISTS) {
        errorMessage.value = GENERIC_LOGIN_ERROR_MESSAGE
        loginForm.value.password = ''
        return
      }

      if (result.reasonCode === REASON_OAUTH_ONLY_ACCOUNT) {
        errorMessage.value = result.message
        return
      }

      if (
        result.requestCode === REQUEST_VALIDATE_ERROR_CODE ||
        result.requestCode === REQUEST_FAIL_ERROR_CODE ||
        result.reasonCode === REASON_RATE_LIMITED ||
        result.reasonCode === REASON_SEND_PENDING
      ) {
        enterRegisterView(loginForm.value.email, loginForm.value.password, { preserveError: true })
        return
      }

      errorMessage.value = result.message
      return
    }

    errorMessage.value = message
    if (message === '密码错误' || message === GENERIC_LOGIN_ERROR_MESSAGE) {
      loginForm.value.password = ''
    }
  }
}
</script>

<template>
  <div
    :class="
      props.embedded
        ? 'w-full'
        : 'w-full h-full flex items-center justify-center bg-slate-50 px-4 py-8'
    "
  >
    <div
      :class="[
        'w-full max-w-[460px] mx-auto',
        props.embedded
          ? 'p-6'
          : 'p-10 border border-slate-200 shadow-[0_16px_48px_rgba(15,23,42,0.08)]',
      ]"
    >
      <div class="mb-6">
        <div class="flex justify-center mb-4">
          <icon-open-agent type="character" :size="248" />
        </div>
        <p class="text-sm text-slate-500 mt-2 text-center">
          {{
            authView === 'login'
              ? '使用邮箱账号登录，继续你的 AI 工作台'
              : authView === 'register'
                ? '使用邮箱完成注册，验证后即可登录'
              : authView === 'registerVerify'
                ? '首次注册需要完成邮箱验证码验证'
                : authView === 'challenge'
                  ? '检测到新的登录环境，请完成邮箱验证码验证'
                  : forgotStep === 1
                    ? '输入您的邮箱'
                    : '输入验证码并设置新密码'
          }}
        </p>
      </div>

      <div
        v-if="authView !== 'forgot' && errorMessage"
        class="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2 mb-4"
      >
        {{ errorMessage }}
      </div>

      <div
        v-if="(authView === 'login' || authView === 'register') && hasOauthOnlyProviders"
        data-testid="oauth-only-suggestions"
        class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 mb-4"
      >
        <p class="text-sm text-slate-700 mb-3">
          该邮箱已绑定第三方登录，可直接使用以下方式继续：
        </p>
        <div class="grid grid-cols-2 gap-2">
          <a-button
            v-if="shouldRenderOauthProvider('google')"
            class="oauth-btn"
            size="large"
            type="outline"
            long
            :loading="providerLoading"
            :disabled="providerLoading"
            @click="googleLogin"
          >
            <template #icon>
              <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
                <path
                  fill="#FFC107"
                  d="M43.611 20.083H42V20H24v8h11.303A12.02 12.02 0 0 1 24 36c-6.627 0-12-5.373-12-12S17.373 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657A19.91 19.91 0 0 0 24 4C12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917Z"
                />
                <path
                  fill="#FF3D00"
                  d="m6.306 14.691 6.571 4.819A11.968 11.968 0 0 1 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657A19.91 19.91 0 0 0 24 4C16.318 4 9.653 8.337 6.306 14.691Z"
                />
                <path
                  fill="#4CAF50"
                  d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.947 11.947 0 0 1 24 36a11.99 11.99 0 0 1-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44Z"
                />
                <path
                  fill="#1976D2"
                  d="M43.611 20.083H42V20H24v8h11.303a12.05 12.05 0 0 1-4.091 5.571l6.19 5.238C40.971 35.489 44 30.203 44 24c0-1.341-.138-2.65-.389-3.917Z"
                />
              </svg>
            </template>
            {{ OAUTH_PROVIDER_LABELS.google }} 登录
          </a-button>

          <a-button
            v-if="shouldRenderOauthProvider('github')"
            class="oauth-btn"
            size="large"
            type="outline"
            long
            :loading="providerLoading"
            :disabled="providerLoading"
            @click="githubLogin"
          >
            <template #icon>
              <span
                class="inline-flex h-[18px] w-[18px] items-center justify-center rounded-full bg-[#24292f] text-white"
              >
                <icon-github :size="12" />
              </span>
            </template>
            {{ OAUTH_PROVIDER_LABELS.github }} 登录
          </a-button>
        </div>
      </div>

      <a-form
        v-if="authView === 'login'"
        :model="loginForm"
        @submit="handleSubmit"
        layout="vertical"
        size="large"
      >
        <a-form-item
          field="email"
          class="login-input !mb-4"
          :rules="[{ type: 'email', required: true, message: '登录/注册账号必须是合法的邮箱' }]"
          :validate-trigger="['change', 'blur']"
          hide-label
        >
          <a-input v-model="loginForm.email" size="large" allow-clear placeholder="登录/注册账号">
            <template #prefix>
              <icon-user class="text-slate-400" />
            </template>
          </a-input>
        </a-form-item>

        <a-form-item
          field="password"
          class="login-input !mb-2"
          :rules="[{ required: true, message: '账号密码不能为空' }]"
          :validate-trigger="['change', 'blur']"
          hide-label
        >
          <a-input-password v-model="loginForm.password" size="large" placeholder="账号密码">
            <template #prefix>
              <icon-lock class="text-slate-400" />
            </template>
          </a-input-password>
        </a-form-item>

        <div class="flex items-center justify-between text-sm text-slate-600 mb-4">
          <a-checkbox v-model="rememberPassword" @change="handleRememberChange">记住密码</a-checkbox>
          <a-link class="!text-slate-500 hover:!text-slate-700" @click="openForgotPassword">
            忘记密码?
          </a-link>
        </div>

        <a-button
          :loading="passwordLoginLoading || prepareRegisterLoading"
          size="large"
          type="primary"
          html-type="submit"
          long
          class="login-submit-btn !text-base !font-medium"
        >
          登录
        </a-button>

        <div class="text-center mt-4">
          <span class="text-sm text-slate-500">没有账号？</span>
          <a-link class="!text-slate-600 hover:!text-slate-800" @click="openRegister">
            邮箱验证码注册
          </a-link>
        </div>

        <div class="grid grid-cols-2 gap-2 mt-5">
          <a-button
            class="oauth-btn"
            size="large"
            type="outline"
            long
            :loading="providerLoading"
            :disabled="providerLoading"
            @click="googleLogin"
          >
            <template #icon>
              <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
                <path
                  fill="#FFC107"
                  d="M43.611 20.083H42V20H24v8h11.303A12.02 12.02 0 0 1 24 36c-6.627 0-12-5.373-12-12S17.373 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657A19.91 19.91 0 0 0 24 4C12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917Z"
                />
                <path
                  fill="#FF3D00"
                  d="m6.306 14.691 6.571 4.819A11.968 11.968 0 0 1 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657A19.91 19.91 0 0 0 24 4C16.318 4 9.653 8.337 6.306 14.691Z"
                />
                <path
                  fill="#4CAF50"
                  d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.947 11.947 0 0 1 24 36a11.99 11.99 0 0 1-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44Z"
                />
                <path
                  fill="#1976D2"
                  d="M43.611 20.083H42V20H24v8h11.303a12.05 12.05 0 0 1-4.091 5.571l6.19 5.238C40.971 35.489 44 30.203 44 24c0-1.341-.138-2.65-.389-3.917Z"
                />
              </svg>
            </template>
            Google
          </a-button>

          <a-button
            class="oauth-btn"
            size="large"
            type="outline"
            long
            :loading="providerLoading"
            :disabled="providerLoading"
            @click="githubLogin"
          >
            <template #icon>
              <span
                class="inline-flex h-[18px] w-[18px] items-center justify-center rounded-full bg-[#24292f] text-white"
              >
                <icon-github :size="12" />
              </span>
            </template>
            GitHub
          </a-button>
        </div>
      </a-form>

      <div v-else-if="authView === 'register'">
        <div class="rounded-xl bg-sky-50 border border-sky-100 px-4 py-3 text-sm text-sky-900 mb-4">
          {{ registerEntryDescription }}
        </div>

        <a-form-item hide-label class="login-input !mb-4">
          <a-input
            v-model="registerForm.email"
            size="large"
            allow-clear
            placeholder="请输入注册邮箱"
            @keyup.enter="handleStartRegister"
          >
            <template #prefix>
              <icon-email class="text-slate-400" />
            </template>
          </a-input>
        </a-form-item>

        <a-form-item hide-label class="login-input !mb-4">
          <a-input-password
            v-model="registerForm.password"
            size="large"
            placeholder="请设置密码(至少一个字母,一个数字,长度8-16位)"
            @keyup.enter="handleStartRegister"
          >
            <template #prefix>
              <icon-lock class="text-slate-400" />
            </template>
          </a-input-password>
        </a-form-item>

        <a-button
          :loading="prepareRegisterLoading"
          size="large"
          type="primary"
          long
          class="login-submit-btn !text-base !font-medium"
          @click="handleStartRegister"
        >
          发送注册验证码
        </a-button>

        <div class="text-center mt-4">
          <span class="text-sm text-slate-500">已有账号？</span>
          <a-link class="!text-slate-600 hover:!text-slate-800" @click="backToLogin">
            返回登录
          </a-link>
        </div>
      </div>

      <div v-else-if="authView === 'registerVerify'">
        <div class="rounded-xl bg-sky-50 border border-sky-100 px-4 py-3 text-sm text-sky-900 mb-4">
          {{ registerDescription }}
        </div>

        <a-form-item hide-label class="login-input !mb-3">
          <a-input v-model="registerForm.email" size="large" readonly>
            <template #prefix>
              <icon-email class="text-slate-400" />
            </template>
          </a-input>
        </a-form-item>

        <a-form-item hide-label class="login-input !mb-4">
          <a-input
            v-model="registerForm.code"
            size="large"
            placeholder="请输入6位验证码"
            maxlength="6"
            @keyup.enter="handleVerifyRegisterAction"
          >
            <template #prefix>
              <icon-safe class="text-slate-400" />
            </template>
            <template #suffix>
              <a-button
                type="text"
                size="mini"
                class="!text-slate-500"
                :loading="prepareRegisterLoading"
                :disabled="registerCountdown > 0"
                @click="handleResendRegisterCode"
              >
                {{ registerCountdownText }}
              </a-button>
            </template>
          </a-input>
        </a-form-item>

        <a-button
          :loading="verifyRegisterLoading"
          size="large"
          type="primary"
          long
          class="login-submit-btn !text-base !font-medium"
          @click="handleVerifyRegisterAction"
        >
          验证并完成注册
        </a-button>

        <div class="text-center mt-4">
          <a-link class="!text-slate-500 hover:!text-slate-700" @click="backToLogin">
            <icon-left />
            返回登录
          </a-link>
        </div>
      </div>

      <div v-else-if="authView === 'challenge'">
        <div class="rounded-xl bg-amber-50 border border-amber-100 px-4 py-3 text-sm text-amber-900 mb-4">
          {{ challengeDescription }}
        </div>

        <a-form-item hide-label class="login-input !mb-4">
          <a-input
            v-model="challengeCode"
            size="large"
            placeholder="请输入6位验证码"
            maxlength="6"
            @keyup.enter="handleVerifyChallenge"
          >
            <template #prefix>
              <icon-safe class="text-slate-400" />
            </template>
            <template #suffix>
              <a-button
                type="text"
                size="mini"
                class="!text-slate-500"
                :loading="resendLoginChallengeLoading"
                :disabled="challengeCountdown > 0"
                @click="handleResendChallengeCode"
              >
                {{ challengeCountdownText }}
              </a-button>
            </template>
          </a-input>
        </a-form-item>

        <a-button
          :loading="verifyLoginChallengeLoading"
          size="large"
          type="primary"
          long
          class="login-submit-btn !text-base !font-medium"
          @click="handleVerifyChallenge"
        >
          完成登录验证
        </a-button>

        <div class="text-center mt-4">
          <a-link class="!text-slate-500 hover:!text-slate-700" @click="backToLogin">
            <icon-left />
            返回登录
          </a-link>
        </div>
      </div>

      <div v-else>
        <div v-if="forgotStep === 1">
          <a-form-item hide-label class="login-input !mb-4">
            <a-input
              v-model="forgotForm.email"
              size="large"
              allow-clear
              placeholder="请输入邮箱"
              @keyup.enter="handleSendCode"
            >
              <template #prefix>
                <icon-email class="text-slate-400" />
              </template>
            </a-input>
          </a-form-item>
          <a-button
            :loading="sendingCode"
            size="large"
            type="primary"
            long
            class="login-submit-btn !text-base !font-medium"
            @click="handleSendCode"
          >
            发送验证码
          </a-button>
        </div>

        <div v-else>
          <a-form-item hide-label class="login-input !mb-3">
            <a-input
              v-model="forgotForm.code"
              size="large"
              placeholder="请输入6位验证码"
              maxlength="6"
              @keyup.enter="handleResetPassword"
            >
              <template #prefix>
                <icon-safe class="text-slate-400" />
              </template>
              <template #suffix>
                <a-button
                  type="text"
                  size="mini"
                  class="!text-slate-500"
                  :disabled="countdown > 0"
                  @click="handleResendCode"
                >
                  {{ countdownText }}
                </a-button>
              </template>
            </a-input>
          </a-form-item>

          <a-form-item hide-label class="login-input !mb-3">
            <a-input-password
              v-model="forgotForm.new_password"
              size="large"
              placeholder="新密码(至少一个字母,一个数字,长度8-16位)"
            >
              <template #prefix>
                <icon-lock class="text-slate-400" />
              </template>
            </a-input-password>
          </a-form-item>

          <a-form-item hide-label class="login-input !mb-3">
            <a-input-password
              v-model="forgotForm.confirm_password"
              size="large"
              placeholder="请再次输入新密码"
              @keyup.enter="handleResetPassword"
            >
              <template #prefix>
                <icon-lock class="text-slate-400" />
              </template>
            </a-input-password>
          </a-form-item>

          <a-button
            :loading="resetting"
            size="large"
            type="primary"
            long
            class="login-submit-btn !text-base !font-medium"
            @click="handleResetPassword"
          >
            重置密码
          </a-button>
        </div>

        <div class="text-center mt-4">
          <a-link class="!text-slate-500 hover:!text-slate-700" @click="handleForgotBack">
            <icon-left />
            {{ forgotStep === 1 ? '返回登录' : '返回上一步' }}
          </a-link>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-input :deep(.arco-input-wrapper) {
  border-radius: 10px;
  background: #f8fafc;
  border-color: #e2e8f0;
}

.login-input :deep(.arco-input-wrapper:hover) {
  border-color: #cbd5e1;
  background: #fff;
}

.login-input :deep(.arco-input-wrapper.arco-input-focus) {
  border-color: #3b82f6;
  background: #fff;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.12);
}

.login-submit-btn {
  border-radius: 10px;
  height: 42px;
}

.oauth-btn {
  border-radius: 10px;
  height: 42px;
  border-color: #e2e8f0;
  color: #334155;
  background: #fff;
}

.oauth-btn:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}
</style>
