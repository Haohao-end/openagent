<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message, type ValidatedError } from '@arco-design/web-vue'
import { usePasswordLogin } from '@/hooks/use-auth'
import { useProvider } from '@/hooks/use-oauth'
import { useCredentialStore } from '@/stores/credential'
import { resetPassword, sendResetCode } from '@/services/auth'
import { getErrorMessage } from '@/utils/error'
import IconOpenAgent from '@/components/icons/IconOpenAgent.vue'

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

const authView = ref<'login' | 'forgot'>('login')
const errorMessage = ref('')
const loginForm = ref({ email: '', password: '' })
const rememberPassword = ref(true)
const forgotStep = ref<1 | 2>(1)
const forgotForm = ref({
  email: '',
  code: '',
  new_password: '',
  confirm_password: '',
})
const sendingCode = ref(false)
const resetting = ref(false)
const countdown = ref(0)
const countdownTimer = ref<number>()
const credentialStore = useCredentialStore()
const router = useRouter()
const { loading: passwordLoginLoading, authorization, handlePasswordLogin } = usePasswordLogin()
const { loading: providerLoading, redirect_url, handleProvider } = useProvider()
const countdownText = computed(() => {
  return countdown.value > 0 ? `${countdown.value}秒后重发` : '发送验证码'
})

const STORAGE_KEY = 'login_credentials'

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

const saveCredentials = () => {
  if (rememberPassword.value) {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        email: loginForm.value.email,
        password: loginForm.value.password,
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
})

onBeforeUnmount(() => {
  if (countdownTimer.value) {
    window.clearInterval(countdownTimer.value)
  }
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
  authView.value = 'forgot'
  forgotForm.value.email = loginForm.value.email
  resetForgotForm()
}

const backToLogin = () => {
  authView.value = 'login'
  resetForgotForm()
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
    await sendResetCode(email)
    Message.success('验证码已发送到您的邮箱,请查收')
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

  const passwordRegex = /^(?=.*[a-zA-Z])(?=.*\d).{8,16}$/
  if (!passwordRegex.test(forgotForm.value.new_password)) {
    Message.error('密码最少包含一个字母,一个数字,并且长度在8~16')
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
    await handlePasswordLogin(loginForm.value.email, loginForm.value.password)
    saveCredentials()
    credentialStore.update(authorization.value)

    if (props.redirectAfterLogin) {
      Message.success('登录成功，正在跳转')
      await router.replace({ path: '/home' })
      return
    }

    Message.success('登录成功')
    emits('success')
  } catch (error: unknown) {
    errorMessage.value = getUserFriendlyErrorMessage(error, '登录失败，请检查邮箱和密码后重试')
    loginForm.value.password = ''
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
              : forgotStep === 1
                ? '输入您的注册邮箱'
                : '输入验证码并设置新密码'
          }}
        </p>
      </div>

      <div
        v-if="authView === 'login' && errorMessage"
        class="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2 mb-4"
      >
        {{ errorMessage }}
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
          :loading="passwordLoginLoading"
          size="large"
          type="primary"
          html-type="submit"
          long
          class="login-submit-btn !text-base !font-medium"
        >
          登录/注册
        </a-button>

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

      <div v-else>
        <div v-if="forgotStep === 1">
          <a-form-item hide-label class="login-input !mb-4">
            <a-input
              v-model="forgotForm.email"
              size="large"
              allow-clear
              placeholder="请输入注册邮箱"
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
