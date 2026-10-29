<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useI18n } from 'vue-i18n'
import { useAccountStore } from '@/stores/account'
import {
  useGetAccountLoginHistory,
  useGetAccountSessions,
  useGetCurrentUser,
  useRevokeAccountSession,
  useRevokeOtherAccountSessions,
  useSendChangeEmailCode,
  useUnbindOAuth,
  useUpdateAvatar,
  useUpdateEmail,
  useUpdateName,
  useUpdatePassword,
} from '@/hooks/use-account'
import { useUploadImage } from '@/hooks/use-upload-file'
import { useProvider } from '@/hooks/use-oauth'
import { DEFAULT_AVATAR_URL } from '@/utils/constants'
import { formatTimestampLong } from '@/utils/time-formatter'
import { copyTextToClipboard } from '@/utils/clipboard'
import { type AccountLoginHistoryItem, type AccountSessionItem } from '@/models/account'
import { getErrorMessage } from '@/utils/error'
import { buildSessionMetaItems } from '@/views/layouts/components/setting-session-display'
import { DEFAULT_LOCALE, type AppLocale, isSupportedLocale, setAppLocale } from '@/i18n'

type SettingsTabKey = 'profile' | 'security' | 'bindings' | 'devices' | 'language'

const DEFAULT_AVATAR = DEFAULT_AVATAR_URL
const OAUTH_ACTION_STORAGE_KEY = 'account_oauth_action'
const providerLabels: Record<string, string> = {
  github: 'GitHub',
  google: 'Google',
}

const props = withDefaults(
  defineProps<{
    visible: boolean
    initialTab?: string
  }>(),
  {
    initialTab: 'profile',
  },
)

const emits = defineEmits<{
  (event: 'update:visible', value: boolean): void
}>()

const { t, locale } = useI18n()
const accountStore = useAccountStore()
const { current_user, loadCurrentUser } = useGetCurrentUser()
const {
  loading: loginHistoryLoading,
  history_state,
  loadAccountLoginHistory,
} = useGetAccountLoginHistory()
const { loading: sessionsLoading, session_state, loadAccountSessions } = useGetAccountSessions()
const { handleUpdateAvatar } = useUpdateAvatar()
const { handleUpdateName } = useUpdateName()
const { handleUpdatePassword } = useUpdatePassword()
const { loading: sendEmailCodeLoading, handleSendChangeEmailCode } = useSendChangeEmailCode()
const { loading: updateEmailLoading, handleUpdateEmail } = useUpdateEmail()
const { handleUnbindOAuth } = useUnbindOAuth()
const { loading: revokeOthersLoading, handleRevokeOtherAccountSessions } =
  useRevokeOtherAccountSessions()
const { handleRevokeAccountSession } = useRevokeAccountSession()
const { image_url, handleUploadImage } = useUploadImage()
const { redirect_url, handleProvider } = useProvider()

const updateName = ref(false)
const updateEmailMode = ref(false)
const selectedTab = ref<SettingsTabKey>('profile')
const bindingLoadingProvider = ref('')
const unbindLoadingProvider = ref('')
const revokingSessionId = ref('')
const emailCodeCountdown = ref(0)
const emailCodeTimer = ref<number>()
const devicePanelError = ref('')
let deviceSecurityRequestId = 0
const historyFilters = ref({
  status: 'all',
  search: '',
  current_page: 1,
  page_size: 5,
})

const normalizeTab = (tab?: string): SettingsTabKey => {
  if (tab === 'security' || tab === 'bindings' || tab === 'devices' || tab === 'language') {
    return tab
  }
  return 'profile'
}

const resolveAvatar = (avatar?: string) => avatar || DEFAULT_AVATAR

const createAccountForm = () => {
  const avatar = resolveAvatar(accountStore.account.avatar)

  return {
    fileList: [{ uid: '1', name: 'avatar', url: avatar }],
    name: accountStore.account.name,
    avatar,
    email: accountStore.account.email,
  }
}

const createSecurityForm = () => ({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const createEmailForm = () => ({
  email: accountStore.account.email,
  code: '',
  current_password: '',
})

const accountForm = ref(createAccountForm())
const securityForm = ref(createSecurityForm())
const emailForm = ref(createEmailForm())

const historyStatusOptions = computed(() => [
  { label: t('settings.history.statusAll'), value: 'all' },
  { label: t('common.status.active'), value: 'active' },
  { label: t('common.status.revoked'), value: 'revoked' },
  { label: t('common.status.expired'), value: 'expired' },
  { label: t('common.status.legacy'), value: 'legacy' },
])

const currentLocale = computed<AppLocale>(() => {
  return isSupportedLocale(locale.value) ? locale.value : DEFAULT_LOCALE
})

const languageOptions = computed(() => [
  {
    value: 'zh-CN' as AppLocale,
    label: t('settings.language.options.zhCN'),
    code: 'zh-CN',
    isDefault: true,
  },
  {
    value: 'en-US' as AppLocale,
    label: t('settings.language.options.enUS'),
    code: 'en-US',
    isDefault: false,
  },
])

const oauthBindings = computed(() => accountStore.account.oauth_bindings ?? [])
const boundProviderCount = computed(
  () => oauthBindings.value.filter((item: { bound: boolean }) => item.bound).length,
)
const needsPasswordSetup = computed(() => !accountStore.account.password_set)
const canUnbindWithoutLockout = computed(
  () => accountStore.account.password_set || boundProviderCount.value > 1,
)
const accountSessions = computed<AccountSessionItem[]>(
  () => (session_state.value.sessions ?? []) as AccountSessionItem[],
)
const loginHistory = computed<AccountLoginHistoryItem[]>(
  () => (history_state.value.history ?? []) as AccountLoginHistoryItem[],
)
const sessionCapable = computed(() => Boolean(session_state.value.session_capable))
const otherSessions = computed(() => accountSessions.value.filter((item) => !item.current))
const currentLegacySession = computed(() =>
  accountSessions.value.find((item) => item.current && item.legacy),
)
const devicePanelLoading = computed(() => sessionsLoading.value || loginHistoryLoading.value)
const latestUnusualLogin = computed<AccountLoginHistoryItem | null>(() => {
  const latestItem = loginHistory.value[0]
  return latestItem?.unusual_ip ? latestItem : null
})
const emailCodeButtonText = computed(() =>
  emailCodeCountdown.value > 0
    ? t('common.actions.resendInSeconds', { count: emailCodeCountdown.value })
    : t('common.actions.sendCode'),
)

const validateEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

const formatIpLocation = (ip?: string, location?: string, emptyText?: string) => {
  const normalizedIp = (ip || '').trim()
  const normalizedLocation = (location || '').trim()

  if (normalizedIp && normalizedLocation) {
    return `${normalizedIp} · ${normalizedLocation}`
  }
  if (normalizedIp) {
    return normalizedIp
  }
  if (normalizedLocation) {
    return normalizedLocation
  }
  return emptyText ?? t('common.status.unknownIp')
}

const clearEmailCodeCountdown = () => {
  if (emailCodeTimer.value) {
    window.clearInterval(emailCodeTimer.value)
    emailCodeTimer.value = undefined
  }
  emailCodeCountdown.value = 0
}

const startEmailCodeCountdown = () => {
  clearEmailCodeCountdown()
  emailCodeCountdown.value = 60
  emailCodeTimer.value = window.setInterval(() => {
    emailCodeCountdown.value -= 1
    if (emailCodeCountdown.value <= 0) {
      clearEmailCodeCountdown()
    }
  }, 1000)
}

const updateAccount = async () => {
  await loadCurrentUser()
  accountStore.update(current_user.value)
}

const loadDeviceSecurityData = async () => {
  const requestId = ++deviceSecurityRequestId
  try {
    await Promise.all([
      loadAccountSessions(),
      loadAccountLoginHistory({
        status: historyFilters.value.status,
        search: historyFilters.value.search.trim(),
        current_page: historyFilters.value.current_page,
        page_size: historyFilters.value.page_size,
      }),
    ])
    if (requestId === deviceSecurityRequestId) devicePanelError.value = ''
  } catch (error: unknown) {
    if (requestId === deviceSecurityRequestId) {
      devicePanelError.value = getErrorMessage(error, t('settings.messages.deviceLoadError'))
    }
  }
}

const resetForms = () => {
  updateName.value = false
  updateEmailMode.value = false
  accountForm.value = createAccountForm()
  securityForm.value = createSecurityForm()
  emailForm.value = createEmailForm()
  historyFilters.value = {
    status: 'all',
    search: '',
    current_page: 1,
    page_size: 5,
  }
  devicePanelError.value = ''
  clearEmailCodeCountdown()
}

const handleCancel = () => emits('update:visible', false)

const handleCopyAccountId = async () => {
  await copyTextToClipboard(accountStore.account.id)
  Message.success(t('settings.messages.copyAccountIdSuccess'))
}

const handleAvatarCustomRequest = (option: any) => {
  const uploadTask = async () => {
    const { fileItem, onSuccess, onError } = option

    try {
      await handleUploadImage(fileItem.file as File)
      accountForm.value.avatar = image_url.value
      onSuccess(image_url.value)

      await handleUpdateAvatar(String(accountForm.value.avatar))
      await updateAccount()
    } catch (error) {
      onError(error)
    }
  }

  void uploadTask()

  return {}
}

const handleSaveName = async () => {
  await handleUpdateName(accountForm.value.name)
  await updateAccount()
  updateName.value = false
}

const handleStartUpdateEmail = () => {
  updateEmailMode.value = true
  emailForm.value = createEmailForm()
}

const handleCancelUpdateEmail = () => {
  updateEmailMode.value = false
  emailForm.value = createEmailForm()
  clearEmailCodeCountdown()
}

const handleSendEmailCode = async () => {
  const email = emailForm.value.email.trim()
  if (!email) {
    Message.error(t('settings.messages.enterNewEmail'))
    return
  }

  if (!validateEmail(email)) {
    Message.error(t('settings.messages.invalidEmail'))
    return
  }

  if (email === accountStore.account.email) {
    Message.error(t('settings.messages.newEmailSameAsCurrent'))
    return
  }

  await handleSendChangeEmailCode(email)
  startEmailCodeCountdown()
}

const handleSaveEmail = async () => {
  const email = emailForm.value.email.trim()
  const code = emailForm.value.code.trim()
  const currentPassword = emailForm.value.current_password.trim()
  if (!email) {
    Message.error(t('settings.messages.enterNewEmail'))
    return
  }

  if (!validateEmail(email)) {
    Message.error(t('settings.messages.invalidEmail'))
    return
  }

  if (!code) {
    Message.error(t('settings.messages.enterCode'))
    return
  }

  if (!needsPasswordSetup.value && !currentPassword) {
    Message.error(t('settings.messages.enterCurrentPasswordForEmailChange'))
    return
  }

  await handleUpdateEmail(email, code, currentPassword)
  await updateAccount()
  updateEmailMode.value = false
  emailForm.value = createEmailForm()
  clearEmailCodeCountdown()
}

const handleSavePassword = async () => {
  const { current_password, new_password, confirm_password } = securityForm.value
  if (!new_password) {
    Message.error(t('settings.messages.enterNewPassword'))
    return
  }

  if (new_password !== confirm_password) {
    Message.error(t('settings.messages.passwordMismatch'))
    return
  }

  const passwordRegex = /^(?=.*[a-zA-Z])(?=.*\d).{8,16}$/
  if (!passwordRegex.test(new_password)) {
    Message.error(t('settings.messages.passwordRuleInvalid'))
    return
  }

  await handleUpdatePassword(current_password, new_password)
  securityForm.value = createSecurityForm()
  await updateAccount()
}

const handleBindProvider = async (providerName: string) => {
  bindingLoadingProvider.value = providerName
  try {
    sessionStorage.setItem(
      OAUTH_ACTION_STORAGE_KEY,
      JSON.stringify({ intent: 'bind', provider: providerName }),
    )
    await handleProvider(providerName)
    window.location.href = redirect_url.value
  } finally {
    bindingLoadingProvider.value = ''
  }
}

const handleUnbindProvider = async (providerName: string) => {
  const providerLabel = providerLabels[providerName] || providerName
  if (!window.confirm(t('settings.messages.confirmUnbind', { provider: providerLabel }))) {
    return
  }

  unbindLoadingProvider.value = providerName
  try {
    await handleUnbindOAuth(providerName)
    await updateAccount()
  } finally {
    unbindLoadingProvider.value = ''
  }
}

const handleRefreshSessions = async () => {
  await loadDeviceSecurityData()
}

const handleLocaleChange = (nextLocale: AppLocale) => {
  setAppLocale(nextLocale)
}

const handleRevokeSessionItem = async (session: AccountSessionItem) => {
  const deviceName = session.device_name || t('common.status.unknownDevice')
  if (!window.confirm(t('settings.messages.confirmRevokeSession', { device: deviceName }))) {
    return
  }

  revokingSessionId.value = session.id
  try {
    await handleRevokeAccountSession(session.id)
    await loadDeviceSecurityData()
  } finally {
    revokingSessionId.value = ''
  }
}

const handleRevokeOthers = async () => {
  if (!sessionCapable.value) {
    Message.warning(t('settings.devices.currentCredentialLegacy'))
    return
  }

  if (!otherSessions.value.length) {
    Message.info(t('settings.devices.noOtherSessions'))
    return
  }

  if (!window.confirm(t('settings.messages.confirmRevokeOthers'))) {
    return
  }

  await handleRevokeOtherAccountSessions()
  await loadDeviceSecurityData()
}

const getLoginHistoryStatusText = (status: AccountLoginHistoryItem['status']) => {
  if (status === 'revoked') return t('common.status.revoked')
  if (status === 'expired') return t('common.status.expired')
  if (status === 'legacy') return t('common.status.legacy')
  return t('common.status.active')
}

const getLoginHistoryStatusColor = (status: AccountLoginHistoryItem['status']) => {
  if (status === 'revoked') return 'gray'
  if (status === 'expired') return 'orange'
  if (status === 'legacy') return 'arcoblue'
  return 'green'
}

const handleHistorySearch = async () => {
  historyFilters.value.current_page = 1
  await loadDeviceSecurityData()
}

const handleHistoryStatusChange = async (value: string | number | boolean) => {
  historyFilters.value.status = String(value || 'all')
  historyFilters.value.current_page = 1
  await loadDeviceSecurityData()
}

const handleHistoryPageChange = async (page: number) => {
  historyFilters.value.current_page = page
  await loadDeviceSecurityData()
}

watch(
  () => props.visible,
  async (newValue) => {
    if (newValue) {
      selectedTab.value = normalizeTab(props.initialTab)
      accountForm.value = createAccountForm()
      emailForm.value = createEmailForm()
      if (selectedTab.value === 'devices') {
        await loadDeviceSecurityData()
      }
      return
    }

    resetForms()
  },
  { immediate: true },
)

watch(
  () => props.initialTab,
  async (newValue) => {
    if (!props.visible) return
    selectedTab.value = normalizeTab(newValue)
    if (selectedTab.value === 'devices') {
      await loadDeviceSecurityData()
    }
  },
)

watch(selectedTab, async (newValue) => {
  if (!props.visible || newValue !== 'devices') return
  await loadDeviceSecurityData()
})

onBeforeUnmount(() => {
  clearEmailCodeCountdown()
})
</script>

<template>
  <a-modal
    :visible="visible"
    hide-title
    :footer="false"
    :width="980"
    modal-class="settings-modal"
    @cancel="handleCancel"
  >
    <a-button
      type="text"
      class="!text-gray-700 absolute right-5 top-5"
      size="small"
      @click="handleCancel"
    >
      <template #icon>
        <icon-close />
      </template>
    </a-button>

    <div class="flex h-[680px] max-h-[calc(100vh-160px)] overflow-hidden">
      <div class="w-[220px] h-full flex-shrink-0 border-r border-gray-100 pr-5">
        <div class="text-xl font-bold text-gray-900 mb-5">{{ $t('settings.title') }}</div>
        <div class="flex flex-col gap-2">
          <button
            type="button"
            :class="[
              'text-left rounded-lg px-4 h-10 transition-colors',
              selectedTab === 'profile'
                ? 'bg-blue-50 text-blue-700'
                : 'text-gray-700 hover:bg-gray-100',
            ]"
            @click="selectedTab = 'profile'"
          >
            {{ $t('settings.tabs.profile') }}
          </button>
          <button
            type="button"
            :class="[
              'text-left rounded-lg px-4 h-10 transition-colors',
              selectedTab === 'security'
                ? 'bg-blue-50 text-blue-700'
                : 'text-gray-700 hover:bg-gray-100',
            ]"
            @click="selectedTab = 'security'"
          >
            {{ $t('settings.tabs.security') }}
          </button>
          <button
            type="button"
            :class="[
              'text-left rounded-lg px-4 h-10 transition-colors',
              selectedTab === 'bindings'
                ? 'bg-blue-50 text-blue-700'
                : 'text-gray-700 hover:bg-gray-100',
            ]"
            @click="selectedTab = 'bindings'"
          >
            {{ $t('settings.tabs.bindings') }}
          </button>
          <button
            type="button"
            :class="[
              'text-left rounded-lg px-4 h-10 transition-colors',
              selectedTab === 'devices'
                ? 'bg-blue-50 text-blue-700'
                : 'text-gray-700 hover:bg-gray-100',
            ]"
            @click="selectedTab = 'devices'"
          >
            {{ $t('settings.tabs.devices') }}
          </button>
          <button
            type="button"
            :class="[
              'text-left rounded-lg px-4 h-10 transition-colors',
              selectedTab === 'language'
                ? 'bg-blue-50 text-blue-700'
                : 'text-gray-700 hover:bg-gray-100',
            ]"
            @click="selectedTab = 'language'"
          >
            {{ $t('settings.tabs.language') }}
          </button>
        </div>
      </div>

      <div class="settings-modal-content flex-1 h-full overflow-y-auto px-8">
        <template v-if="selectedTab === 'profile'">
          <div class="text-xl font-bold text-gray-900 mb-2">{{ $t('settings.profile.title') }}</div>
          <div class="text-sm text-gray-500 mb-6">{{ $t('settings.profile.description') }}</div>

          <a-form :model="{}" layout="vertical">
            <a-form-item field="avatar">
              <template #label>
                <div class="flex items-center gap-1">
                  {{ $t('settings.profile.avatar') }}
                  <div class="text-red-700">*</div>
                </div>
              </template>
              <a-upload
                v-model:file-list="accountForm.fileList"
                list-type="picture-card"
                :limit="1"
                image-preview
                :custom-request="handleAvatarCustomRequest"
              />
            </a-form-item>

            <a-form-item field="name">
              <template #label>
                <div class="flex items-center gap-1">
                  {{ $t('settings.profile.name') }}
                  <div class="text-red-700">*</div>
                </div>
              </template>
              <div v-if="updateName" class="flex items-center gap-2 w-full">
                <a-input
                  v-model="accountForm.name"
                  :placeholder="t('settings.profile.updateNamePlaceholder')"
                  :max-length="30"
                />
                <div class="flex items-center gap-1">
                  <a-button
                    class="rounded-lg"
                    @click="
                      () => {
                        updateName = false
                        accountForm.name = accountStore.account.name
                      }
                    "
                  >
                    {{ $t('common.actions.cancel') }}
                  </a-button>
                  <a-button type="primary" class="rounded-lg" @click="handleSaveName">
                    {{ $t('common.actions.save') }}
                  </a-button>
                </div>
              </div>
              <div v-else class="flex items-center gap-1">
                <div>{{ accountStore.account.name }}</div>
                <a-button size="mini" type="text" class="!text-gray-700" @click="updateName = true">
                  <template #icon>
                    <icon-edit />
                  </template>
                </a-button>
              </div>
            </a-form-item>

            <a-form-item field="email" :label="t('settings.profile.email')">
              <div class="w-full flex flex-col gap-3">
                <div v-if="!updateEmailMode" class="flex items-center gap-2">
                  <a-input readonly v-model="accountForm.email" />
                  <a-button class="rounded-lg flex-shrink-0" @click="handleStartUpdateEmail">
                    {{ $t('settings.profile.changeEmail') }}
                  </a-button>
                </div>
                <div
                  v-else
                  class="rounded-xl border border-blue-100 bg-blue-50/50 px-4 py-4 flex flex-col gap-3"
                >
                  <a-input
                    v-model="emailForm.email"
                    :placeholder="t('settings.profile.newEmailPlaceholder')"
                  />
                  <a-input-password
                    v-if="!needsPasswordSetup"
                    v-model="emailForm.current_password"
                    :placeholder="t('settings.profile.currentPasswordPlaceholder')"
                  />
                  <div class="flex items-center gap-2">
                    <a-input
                      v-model="emailForm.code"
                      :placeholder="t('settings.profile.codePlaceholder')"
                    />
                    <a-button
                      class="rounded-lg flex-shrink-0"
                      :loading="sendEmailCodeLoading"
                      :disabled="emailCodeCountdown > 0"
                      @click="handleSendEmailCode"
                    >
                      {{ emailCodeButtonText }}
                    </a-button>
                  </div>
                  <div class="flex items-center gap-2">
                    <a-button class="rounded-lg" @click="handleCancelUpdateEmail">
                      {{ $t('common.actions.cancel') }}
                    </a-button>
                    <a-button
                      type="primary"
                      class="rounded-lg"
                      :loading="updateEmailLoading"
                      @click="handleSaveEmail"
                    >
                      {{ $t('settings.profile.confirmChangeEmail') }}
                    </a-button>
                  </div>
                  <div class="text-xs text-gray-500">
                    {{
                      needsPasswordSetup
                        ? $t('settings.profile.emailHintWithoutPassword')
                        : $t('settings.profile.emailHintWithPassword')
                    }}
                  </div>
                </div>
              </div>
            </a-form-item>
          </a-form>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
            <div class="rounded-xl border border-gray-100 bg-gray-50 px-4 py-4">
              <div class="text-sm text-gray-500 mb-1">{{ $t('settings.profile.accountId') }}</div>
              <div class="flex items-center gap-2">
                <div class="text-sm text-gray-900 break-all">{{ accountStore.account.id }}</div>
                <a-button
                  type="text"
                  size="mini"
                  class="!text-gray-700"
                  @click="handleCopyAccountId"
                >
                  <template #icon>
                    <icon-copy />
                  </template>
                </a-button>
              </div>
            </div>

            <div class="rounded-xl border border-gray-100 bg-gray-50 px-4 py-4">
              <div class="text-sm text-gray-500 mb-1">
                {{ $t('settings.profile.registeredAt') }}
              </div>
              <div class="text-sm text-gray-900">
                {{
                  formatTimestampLong(accountStore.account.created_at) ||
                  $t('common.status.noRecord')
                }}
              </div>
            </div>

            <div class="rounded-xl border border-gray-100 bg-gray-50 px-4 py-4">
              <div class="text-sm text-gray-500 mb-1">{{ $t('settings.profile.lastLoginAt') }}</div>
              <div class="text-sm text-gray-900">
                {{
                  formatTimestampLong(accountStore.account.last_login_at) ||
                  $t('common.status.noRecord')
                }}
              </div>
            </div>

            <div class="rounded-xl border border-gray-100 bg-gray-50 px-4 py-4">
              <div class="text-sm text-gray-500 mb-1">{{ $t('settings.profile.lastLoginIp') }}</div>
              <div class="text-sm text-gray-900">
                {{
                  formatIpLocation(
                    accountStore.account.last_login_ip,
                    accountStore.account.last_login_location,
                    t('common.status.noRecord'),
                  )
                }}
              </div>
            </div>
          </div>
        </template>

        <template v-else-if="selectedTab === 'security'">
          <div class="text-xl font-bold text-gray-900 mb-2">
            {{ $t('settings.security.title') }}
          </div>
          <div class="text-sm text-gray-500 mb-6">{{ $t('settings.security.description') }}</div>

          <div class="rounded-xl border border-gray-100 bg-gray-50 px-4 py-4 mb-5">
            <div class="text-sm text-gray-500 mb-1">
              {{ $t('settings.security.passwordStatus') }}
            </div>
            <div class="text-sm text-gray-900">
              {{
                needsPasswordSetup
                  ? $t('settings.security.passwordUnset')
                  : $t('settings.security.passwordSet')
              }}
            </div>
            <div class="text-xs text-gray-500 mt-2">
              {{
                needsPasswordSetup
                  ? $t('settings.security.passwordAdviceWithout')
                  : $t('settings.security.passwordAdviceWith')
              }}
            </div>
          </div>

          <a-form :model="securityForm" layout="vertical">
            <a-form-item
              v-if="!needsPasswordSetup"
              field="current_password"
              :label="t('settings.security.currentPassword')"
            >
              <a-input-password
                v-model="securityForm.current_password"
                :placeholder="t('settings.security.currentPasswordPlaceholder')"
              />
            </a-form-item>
            <a-form-item
              field="new_password"
              :label="
                needsPasswordSetup
                  ? t('settings.security.setPassword')
                  : t('settings.security.newPassword')
              "
            >
              <a-input-password
                v-model="securityForm.new_password"
                :placeholder="t('settings.security.newPasswordPlaceholder')"
              />
            </a-form-item>
            <a-form-item
              field="confirm_password"
              :label="t('settings.security.confirmNewPassword')"
            >
              <a-input-password
                v-model="securityForm.confirm_password"
                :placeholder="t('settings.security.confirmNewPasswordPlaceholder')"
              />
            </a-form-item>
          </a-form>

          <div
            class="flex items-center justify-between rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 mt-6"
          >
            <div class="text-sm text-amber-900">
              {{ $t('settings.security.forgotPasswordHint') }}
            </div>
            <a-button type="primary" class="rounded-lg" @click="handleSavePassword">
              {{
                needsPasswordSetup
                  ? $t('settings.security.submitSetPassword')
                  : $t('settings.security.submitUpdatePassword')
              }}
            </a-button>
          </div>
        </template>

        <template v-else-if="selectedTab === 'bindings'">
          <div class="text-xl font-bold text-gray-900 mb-2">
            {{ $t('settings.bindings.title') }}
          </div>
          <div class="text-sm text-gray-500 mb-6">{{ $t('settings.bindings.description') }}</div>

          <div class="flex flex-col gap-4">
            <div
              v-for="binding in oauthBindings"
              :key="binding.provider"
              class="rounded-xl border border-gray-100 bg-white px-4 py-4"
            >
              <div class="flex items-center justify-between gap-4">
                <div>
                  <div class="text-base font-semibold text-gray-900">
                    {{ providerLabels[binding.provider] || binding.provider }}
                  </div>
                  <div class="text-sm text-gray-500 mt-1">
                    {{
                      binding.bound
                        ? $t('settings.bindings.boundAt', {
                            time:
                              formatTimestampLong(binding.bound_at) || $t('common.status.unknown'),
                          })
                        : $t('settings.bindings.unboundHint')
                    }}
                  </div>
                  <div
                    v-if="binding.bound && !canUnbindWithoutLockout"
                    class="text-xs text-amber-600 mt-2"
                  >
                    {{ $t('settings.bindings.lockoutWarning') }}
                  </div>
                </div>

                <div class="flex items-center gap-2">
                  <a-tag :color="binding.bound ? 'green' : 'gray'">
                    {{
                      binding.bound
                        ? $t('settings.bindings.bound')
                        : $t('settings.bindings.unbound')
                    }}
                  </a-tag>
                  <a-button
                    v-if="!binding.bound"
                    type="primary"
                    class="rounded-lg"
                    :loading="bindingLoadingProvider === binding.provider"
                    @click="handleBindProvider(binding.provider)"
                  >
                    {{ $t('settings.bindings.goBind') }}
                  </a-button>
                  <a-button
                    v-else
                    status="danger"
                    class="rounded-lg"
                    :loading="unbindLoadingProvider === binding.provider"
                    :disabled="!canUnbindWithoutLockout"
                    @click="handleUnbindProvider(binding.provider)"
                  >
                    {{ $t('settings.bindings.unbind') }}
                  </a-button>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-else-if="selectedTab === 'language'">
          <div class="text-xl font-bold text-gray-900 mb-2">
            {{ $t('settings.language.title') }}
          </div>
          <div class="text-sm text-gray-500 mb-6">
            {{ $t('settings.language.description') }}
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              v-for="option in languageOptions"
              :key="option.value"
              type="button"
              class="rounded-xl border px-4 py-4 text-left transition-colors"
              :class="
                currentLocale === option.value
                  ? 'border-blue-200 bg-blue-50 text-blue-900'
                  : 'border-gray-200 bg-white text-gray-900 hover:border-gray-300 hover:bg-gray-50'
              "
              @click="handleLocaleChange(option.value)"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="flex items-start gap-3">
                  <icon-language class="text-base" />
                  <div class="flex flex-col gap-1">
                    <div class="flex items-center gap-2">
                      <div class="text-base font-semibold">{{ option.label }}</div>
                      <a-tag v-if="option.isDefault" size="small" color="arcoblue">
                        {{ $t('settings.language.defaultTag') }}
                      </a-tag>
                    </div>
                    <div class="text-xs text-gray-500">{{ option.code }}</div>
                  </div>
                </div>
              </div>
            </button>
          </div>
        </template>

        <template v-else>
          <div class="flex items-start justify-between gap-4 mb-6">
            <div>
              <div class="text-xl font-bold text-gray-900 mb-2">
                {{ $t('settings.devices.title') }}
              </div>
              <div class="text-sm text-gray-500">{{ $t('settings.devices.description') }}</div>
            </div>
            <div class="flex items-center gap-2">
              <a-button
                class="rounded-lg"
                :loading="devicePanelLoading"
                @click="handleRefreshSessions"
              >
                {{ $t('common.actions.refresh') }}
              </a-button>
              <a-button
                type="primary"
                status="danger"
                class="rounded-lg"
                :loading="revokeOthersLoading"
                :disabled="!sessionCapable || otherSessions.length === 0"
                @click="handleRevokeOthers"
              >
                {{ $t('settings.devices.revokeOthers') }}
              </a-button>
            </div>
          </div>

          <div
            v-if="!sessionCapable"
            class="rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-900 mb-5"
          >
            {{ $t('settings.devices.legacySessionCapableWarning') }}
          </div>

          <div
            v-if="currentLegacySession"
            class="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-900 mb-5"
          >
            {{ $t('settings.devices.currentLegacyWarning') }}
          </div>

          <div
            v-if="devicePanelError"
            class="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-900 mb-5"
          >
            {{ devicePanelError }}
          </div>

          <div
            v-if="latestUnusualLogin"
            class="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-900 mb-5"
          >
            {{
              $t('settings.devices.latestUnusualLoginAlert', {
                ip: formatIpLocation(latestUnusualLogin.ip, latestUnusualLogin.location),
                time:
                  formatTimestampLong(latestUnusualLogin.created_at) || $t('common.status.unknown'),
              })
            }}
          </div>

          <div class="text-base font-semibold text-gray-900 mb-3">
            {{ $t('settings.devices.onlineDevices') }}
          </div>

          <div
            v-if="!accountSessions.length"
            class="rounded-xl border border-dashed border-gray-200 px-6 py-10 text-center text-sm text-gray-500"
          >
            {{ devicePanelError || $t('settings.devices.noManageableDevices') }}
          </div>

          <div v-else class="flex flex-col gap-4">
            <div
              v-for="session in accountSessions"
              :key="session.id"
              class="rounded-xl border border-gray-100 bg-white px-4 py-4"
            >
              <div class="flex items-start justify-between gap-4">
                <div class="min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <div class="text-base font-semibold text-gray-900">
                      {{ session.device_name || $t('common.status.unknownDevice') }}
                    </div>
                    <a-tag :color="session.current ? 'arcoblue' : 'gray'">
                      {{
                        session.current
                          ? $t('settings.devices.currentDeviceTag')
                          : $t('settings.devices.onlineSessionTag')
                      }}
                    </a-tag>
                    <a-tag v-if="session.legacy" color="arcoblue">{{
                      $t('common.status.legacy')
                    }}</a-tag>
                  </div>
                  <div class="text-sm text-gray-500 mt-1">
                    {{ formatIpLocation(session.ip, session.location) }}
                  </div>
                  <div class="text-xs text-gray-500 mt-2 break-all">
                    {{ session.user_agent || $t('common.status.unknown') }}
                  </div>
                </div>

                <a-button
                  v-if="!session.current"
                  status="danger"
                  class="rounded-lg flex-shrink-0"
                  :loading="revokingSessionId === session.id"
                  @click="handleRevokeSessionItem(session)"
                >
                  {{ $t('settings.devices.revoke') }}
                </a-button>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
                <div
                  v-for="meta in buildSessionMetaItems(session, t)"
                  :key="meta.label"
                  class="rounded-lg bg-gray-50 px-3 py-3"
                >
                  <div class="text-xs text-gray-500 mb-1">{{ meta.label }}</div>
                  <div class="text-sm text-gray-900">{{ meta.value }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="text-base font-semibold text-gray-900 mt-8 mb-3">
            {{ $t('settings.devices.recentLoginHistory') }}
          </div>

          <div class="flex flex-col md:flex-row gap-3 mb-4">
            <a-input-search
              v-model="historyFilters.search"
              allow-clear
              :placeholder="t('settings.devices.searchPlaceholder')"
              class="md:max-w-[320px]"
              @search="handleHistorySearch"
            />
            <a-select
              v-model:model-value="historyFilters.status"
              :options="historyStatusOptions"
              class="md:w-[180px]"
              @change="handleHistoryStatusChange"
            />
          </div>

          <div
            v-if="!loginHistory.length"
            class="rounded-xl border border-dashed border-gray-200 px-6 py-10 text-center text-sm text-gray-500"
          >
            {{ devicePanelError || $t('settings.devices.noLoginHistory') }}
          </div>

          <div v-else class="flex flex-col gap-3">
            <div
              v-for="history in loginHistory"
              :key="history.id"
              class="rounded-xl border border-gray-100 bg-white px-4 py-4"
            >
              <div class="flex items-start justify-between gap-4">
                <div class="min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <div class="text-base font-semibold text-gray-900">
                      {{ history.device_name || $t('common.status.unknownDevice') }}
                    </div>
                    <a-tag v-if="history.current" color="arcoblue">
                      {{ $t('settings.devices.currentDeviceTag') }}
                    </a-tag>
                    <a-tag v-if="history.legacy" color="arcoblue">{{
                      $t('common.status.legacy')
                    }}</a-tag>
                    <a-tag :color="getLoginHistoryStatusColor(history.status)">
                      {{ getLoginHistoryStatusText(history.status) }}
                    </a-tag>
                    <a-tag v-if="history.unusual_ip" color="red">
                      {{ $t('settings.devices.newIpTag') }}
                    </a-tag>
                  </div>
                  <div class="text-sm text-gray-500 mt-1">
                    {{ formatIpLocation(history.ip, history.location) }}
                  </div>
                  <div class="text-xs text-gray-500 mt-2 break-all">
                    {{ history.user_agent || $t('common.status.unknown') }}
                  </div>
                </div>

                <div class="text-right text-xs text-gray-500 flex-shrink-0">
                  <div>
                    {{
                      $t('settings.devices.loginAt', {
                        time:
                          formatTimestampLong(history.created_at) || $t('common.status.noRecord'),
                      })
                    }}
                  </div>
                  <div class="mt-1">
                    {{
                      $t('settings.devices.lastActiveAt', {
                        time:
                          formatTimestampLong(history.last_active_at) ||
                          $t('common.status.noRecord'),
                      })
                    }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div
            v-if="history_state.total > historyFilters.page_size"
            class="flex justify-center mt-5"
          >
            <a-pagination
              :current="historyFilters.current_page"
              :page-size="historyFilters.page_size"
              :total="history_state.total"
              show-total
              @change="handleHistoryPageChange"
            />
          </div>
        </template>
      </div>
    </div>
  </a-modal>
</template>

<style>
.settings-modal .arco-modal-body {
  overflow: hidden;
}

.settings-modal-content {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.settings-modal-content::-webkit-scrollbar {
  display: none;
}
</style>
