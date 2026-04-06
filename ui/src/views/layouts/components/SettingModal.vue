<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
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

type SettingsTabKey = 'profile' | 'security' | 'bindings' | 'devices'

const DEFAULT_AVATAR = DEFAULT_AVATAR_URL
const OAUTH_ACTION_STORAGE_KEY = 'account_oauth_action'
const providerLabels: Record<string, string> = {
  github: 'GitHub',
  google: 'Google',
}
const historyStatusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '有效', value: 'active' },
  { label: '已下线', value: 'revoked' },
  { label: '已过期', value: 'expired' },
  { label: '旧凭证', value: 'legacy' },
]

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

const accountStore = useAccountStore()
const { current_user, loadCurrentUser } = useGetCurrentUser()
const { loading: loginHistoryLoading, history_state, loadAccountLoginHistory } =
  useGetAccountLoginHistory()
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
const historyFilters = ref({
  status: 'all',
  search: '',
  current_page: 1,
  page_size: 5,
})

const normalizeTab = (tab?: string): SettingsTabKey => {
  if (tab === 'security' || tab === 'bindings' || tab === 'devices') return tab
  return 'profile'
}

const resolveAvatar = (avatar?: string) => avatar || DEFAULT_AVATAR

const createAccountForm = () => {
  const avatar = resolveAvatar(accountStore.account.avatar)

  return {
    fileList: [{ uid: '1', name: '账号头像', url: avatar }],
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

const oauthBindings = computed(() => accountStore.account.oauth_bindings ?? [])
const boundProviderCount = computed(() =>
  oauthBindings.value.filter((item: { bound: boolean }) => item.bound).length,
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
  emailCodeCountdown.value > 0 ? `${emailCodeCountdown.value}秒后重发` : '发送验证码',
)

const validateEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

const formatIpLocation = (ip?: string, location?: string, emptyText: string = '未知 IP') => {
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
  return emptyText
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
    devicePanelError.value = ''
  } catch (error: unknown) {
    devicePanelError.value = getErrorMessage(error, '登录设备数据加载失败，请刷新后重试')
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
  Message.success('账号 ID 已复制')
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
    Message.error('请输入新邮箱地址')
    return
  }

  if (!validateEmail(email)) {
    Message.error('请输入有效的邮箱地址')
    return
  }

  if (email === accountStore.account.email) {
    Message.error('新邮箱不能与当前邮箱相同')
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
    Message.error('请输入新邮箱地址')
    return
  }

  if (!validateEmail(email)) {
    Message.error('请输入有效的邮箱地址')
    return
  }

  if (!code) {
    Message.error('请输入验证码')
    return
  }

  if (!needsPasswordSetup.value && !currentPassword) {
    Message.error('请输入当前密码以确认换绑邮箱')
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
    Message.error('请输入新密码')
    return
  }

  if (new_password !== confirm_password) {
    Message.error('两次输入的新密码不一致')
    return
  }

  const passwordRegex = /^(?=.*[a-zA-Z])(?=.*\d).{8,16}$/
  if (!passwordRegex.test(new_password)) {
    Message.error('密码最少包含一个字母、一个数字，并且长度在8到16位')
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
  if (
    !window.confirm(
      `确认解绑 ${providerLabel} 吗？解绑后将无法继续使用该方式登录当前账号。`,
    )
  ) {
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

const handleRevokeSessionItem = async (session: AccountSessionItem) => {
  if (
    !window.confirm(
      `确认下线 ${session.device_name || '该设备'} 吗？下线后该设备需要重新登录。`,
    )
  ) {
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
    Message.warning('当前登录凭证较旧，请重新登录后再管理其他设备')
    return
  }

  if (!otherSessions.value.length) {
    Message.info('当前没有其他在线设备')
    return
  }

  if (!window.confirm('确认下线除当前设备外的其他所有登录设备吗？')) {
    return
  }

  await handleRevokeOtherAccountSessions()
  await loadDeviceSecurityData()
}

const getLoginHistoryStatusText = (status: AccountLoginHistoryItem['status']) => {
  if (status === 'revoked') return '已下线'
  if (status === 'expired') return '已过期'
  if (status === 'legacy') return '旧凭证'
  return '有效'
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

watch(
  selectedTab,
  async (newValue) => {
    if (!props.visible || newValue !== 'devices') return
    await loadDeviceSecurityData()
  },
)

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
        <div class="text-xl font-bold text-gray-900 mb-5">设置中心</div>
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
            基本资料
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
            安全中心
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
            账号绑定
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
            登录设备
          </button>
        </div>
      </div>

      <div class="settings-modal-content flex-1 h-full overflow-y-auto px-8">
        <template v-if="selectedTab === 'profile'">
          <div class="text-xl font-bold text-gray-900 mb-2">基本资料</div>
          <div class="text-sm text-gray-500 mb-6">维护你的公开信息、基础账号资料和绑定邮箱。</div>

          <a-form :model="{}" layout="vertical">
            <a-form-item field="avatar">
              <template #label>
                <div class="flex items-center gap-1">
                  账号头像
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
                  账号昵称
                  <div class="text-red-700">*</div>
                </div>
              </template>
              <div v-if="updateName" class="flex items-center gap-2 w-full">
                <a-input
                  v-model="accountForm.name"
                  placeholder="请输入账号名称"
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
                    取消
                  </a-button>
                  <a-button type="primary" class="rounded-lg" @click="handleSaveName">
                    保存
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

            <a-form-item field="email" label="绑定邮箱">
              <div class="w-full flex flex-col gap-3">
                <div v-if="!updateEmailMode" class="flex items-center gap-2">
                  <a-input readonly v-model="accountForm.email" />
                  <a-button class="rounded-lg flex-shrink-0" @click="handleStartUpdateEmail">
                    换绑邮箱
                  </a-button>
                </div>
                <div
                  v-else
                  class="rounded-xl border border-blue-100 bg-blue-50/50 px-4 py-4 flex flex-col gap-3"
                >
                  <a-input v-model="emailForm.email" placeholder="请输入新邮箱地址" />
                  <a-input-password
                    v-if="!needsPasswordSetup"
                    v-model="emailForm.current_password"
                    placeholder="请输入当前密码完成二次确认"
                  />
                  <div class="flex items-center gap-2">
                    <a-input v-model="emailForm.code" placeholder="请输入6位验证码" />
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
                      取消
                    </a-button>
                    <a-button
                      type="primary"
                      class="rounded-lg"
                      :loading="updateEmailLoading"
                      @click="handleSaveEmail"
                    >
                      确认换绑
                    </a-button>
                  </div>
                  <div class="text-xs text-gray-500">
                    {{
                      needsPasswordSetup
                        ? '验证码会发送到新邮箱，验证通过后会立即替换当前绑定邮箱。'
                        : '验证码会发送到新邮箱；提交时还需要输入当前密码完成二次确认。'
                    }}
                  </div>
                </div>
              </div>
            </a-form-item>
          </a-form>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
            <div class="rounded-xl border border-gray-100 bg-gray-50 px-4 py-4">
              <div class="text-sm text-gray-500 mb-1">账号 ID</div>
              <div class="flex items-center gap-2">
                <div class="text-sm text-gray-900 break-all">{{ accountStore.account.id }}</div>
                <a-button type="text" size="mini" class="!text-gray-700" @click="handleCopyAccountId">
                  <template #icon>
                    <icon-copy />
                  </template>
                </a-button>
              </div>
            </div>

            <div class="rounded-xl border border-gray-100 bg-gray-50 px-4 py-4">
              <div class="text-sm text-gray-500 mb-1">注册时间</div>
              <div class="text-sm text-gray-900">
                {{ formatTimestampLong(accountStore.account.created_at) || '暂无记录' }}
              </div>
            </div>

            <div class="rounded-xl border border-gray-100 bg-gray-50 px-4 py-4">
              <div class="text-sm text-gray-500 mb-1">最近登录时间</div>
              <div class="text-sm text-gray-900">
                {{ formatTimestampLong(accountStore.account.last_login_at) || '暂无记录' }}
              </div>
            </div>

            <div class="rounded-xl border border-gray-100 bg-gray-50 px-4 py-4">
              <div class="text-sm text-gray-500 mb-1">最近登录 IP</div>
              <div class="text-sm text-gray-900">
                {{
                  formatIpLocation(
                    accountStore.account.last_login_ip,
                    accountStore.account.last_login_location,
                    '暂无记录',
                  )
                }}
              </div>
            </div>
          </div>
        </template>

        <template v-else-if="selectedTab === 'security'">
          <div class="text-xl font-bold text-gray-900 mb-2">安全中心</div>
          <div class="text-sm text-gray-500 mb-6">设置登录密码，并查看当前账号的安全状态。</div>

          <div class="rounded-xl border border-gray-100 bg-gray-50 px-4 py-4 mb-5">
            <div class="text-sm text-gray-500 mb-1">密码状态</div>
            <div class="text-sm text-gray-900">
              {{ needsPasswordSetup ? '未设置密码' : '已设置密码' }}
            </div>
            <div class="text-xs text-gray-500 mt-2">
              {{ needsPasswordSetup ? '建议补充登录密码，避免只依赖第三方登录。' : '修改密码后，下次登录将使用新密码。' }}
            </div>
          </div>

          <a-form :model="securityForm" layout="vertical">
            <a-form-item v-if="!needsPasswordSetup" field="current_password" label="当前密码">
              <a-input-password
                v-model="securityForm.current_password"
                placeholder="请输入当前密码"
              />
            </a-form-item>
            <a-form-item field="new_password" :label="needsPasswordSetup ? '设置登录密码' : '新密码'">
              <a-input-password
                v-model="securityForm.new_password"
                placeholder="至少包含一个字母和一个数字，长度 8 到 16 位"
              />
            </a-form-item>
            <a-form-item field="confirm_password" label="确认新密码">
              <a-input-password
                v-model="securityForm.confirm_password"
                placeholder="请再次输入新密码"
              />
            </a-form-item>
          </a-form>

          <div class="flex items-center justify-between rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 mt-6">
            <div class="text-sm text-amber-900">忘记密码时，可在登录页使用邮箱验证码完成重置。</div>
            <a-button type="primary" class="rounded-lg" @click="handleSavePassword">
              {{ needsPasswordSetup ? '设置密码' : '更新密码' }}
            </a-button>
          </div>
        </template>

        <template v-else-if="selectedTab === 'bindings'">
          <div class="text-xl font-bold text-gray-900 mb-2">账号绑定</div>
          <div class="text-sm text-gray-500 mb-6">管理第三方登录方式，并避免账号被单一路径锁死。</div>

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
                        ? `已绑定，绑定时间 ${formatTimestampLong(binding.bound_at) || '未知'}`
                        : '未绑定，可用于快捷登录当前账号'
                    }}
                  </div>
                  <div
                    v-if="binding.bound && !canUnbindWithoutLockout"
                    class="text-xs text-amber-600 mt-2"
                  >
                    当前账号没有可用密码，也没有其他已绑定方式。请先设置密码或绑定另一种方式，再解绑。
                  </div>
                </div>

                <div class="flex items-center gap-2">
                  <a-tag :color="binding.bound ? 'green' : 'gray'">
                    {{ binding.bound ? '已绑定' : '未绑定' }}
                  </a-tag>
                  <a-button
                    v-if="!binding.bound"
                    type="primary"
                    class="rounded-lg"
                    :loading="bindingLoadingProvider === binding.provider"
                    @click="handleBindProvider(binding.provider)"
                  >
                    去绑定
                  </a-button>
                  <a-button
                    v-else
                    status="danger"
                    class="rounded-lg"
                    :loading="unbindLoadingProvider === binding.provider"
                    :disabled="!canUnbindWithoutLockout"
                    @click="handleUnbindProvider(binding.provider)"
                  >
                    解绑
                  </a-button>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="flex items-start justify-between gap-4 mb-6">
            <div>
              <div class="text-xl font-bold text-gray-900 mb-2">登录设备</div>
              <div class="text-sm text-gray-500">查看在线设备、最近登录历史，以及新 IP 登录风险提醒。</div>
            </div>
            <div class="flex items-center gap-2">
              <a-button class="rounded-lg" :loading="devicePanelLoading" @click="handleRefreshSessions">
                刷新
              </a-button>
              <a-button
                type="primary"
                status="danger"
                class="rounded-lg"
                :loading="revokeOthersLoading"
                :disabled="!sessionCapable || otherSessions.length === 0"
                @click="handleRevokeOthers"
              >
                下线其他设备
              </a-button>
            </div>
          </div>

          <div
            v-if="!sessionCapable"
            class="rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-900 mb-5"
          >
            当前登录凭证较旧，请重新登录后再使用“下线其他设备”能力；你仍然可以查看现有会话并逐个下线。
          </div>

          <div
            v-if="currentLegacySession"
            class="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-900 mb-5"
          >
            当前设备仍在使用旧版登录凭证，系统暂时无法准确展示首次登录时间和会话到期时间；重新登录后可查看完整会话信息。
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
            检测到最近一次登录来自新 IP
            <span class="font-medium">
              {{ formatIpLocation(latestUnusualLogin.ip, latestUnusualLogin.location) }}
            </span>
            ，时间
            <span class="font-medium">
              {{ formatTimestampLong(latestUnusualLogin.created_at) || '未知' }}
            </span>
            。如果不是你本人操作，请立即修改密码并下线其他设备；系统也会向绑定邮箱发送提醒。
          </div>

          <div class="text-base font-semibold text-gray-900 mb-3">在线设备</div>

          <div
            v-if="!accountSessions.length"
            class="rounded-xl border border-dashed border-gray-200 px-6 py-10 text-center text-sm text-gray-500"
          >
            {{ devicePanelError ? '登录设备数据加载失败，请刷新后重试' : '暂无可管理的登录设备' }}
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
                      {{ session.device_name || '未知设备' }}
                    </div>
                    <a-tag :color="session.current ? 'arcoblue' : 'gray'">
                      {{ session.current ? '当前设备' : '在线会话' }}
                    </a-tag>
                    <a-tag v-if="session.legacy" color="arcoblue">旧凭证</a-tag>
                  </div>
                  <div class="text-sm text-gray-500 mt-1">
                    {{ formatIpLocation(session.ip, session.location) }}
                  </div>
                  <div class="text-xs text-gray-500 mt-2 break-all">
                    {{ session.user_agent || 'unknown' }}
                  </div>
                </div>

                <a-button
                  v-if="!session.current"
                  status="danger"
                  class="rounded-lg flex-shrink-0"
                  :loading="revokingSessionId === session.id"
                  @click="handleRevokeSessionItem(session)"
                >
                  下线
                </a-button>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
                <div
                  v-for="meta in buildSessionMetaItems(session)"
                  :key="meta.label"
                  class="rounded-lg bg-gray-50 px-3 py-3"
                >
                  <div class="text-xs text-gray-500 mb-1">{{ meta.label }}</div>
                  <div class="text-sm text-gray-900">{{ meta.value }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="text-base font-semibold text-gray-900 mt-8 mb-3">最近登录历史</div>

          <div class="flex flex-col md:flex-row gap-3 mb-4">
            <a-input-search
              v-model="historyFilters.search"
              allow-clear
              placeholder="搜索 IP、地点、设备或浏览器"
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
            {{ devicePanelError ? '登录历史数据加载失败，请刷新后重试' : '暂无登录历史' }}
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
                      {{ history.device_name || '未知设备' }}
                    </div>
                    <a-tag v-if="history.current" color="arcoblue">当前设备</a-tag>
                    <a-tag v-if="history.legacy" color="arcoblue">旧凭证</a-tag>
                    <a-tag :color="getLoginHistoryStatusColor(history.status)">
                      {{ getLoginHistoryStatusText(history.status) }}
                    </a-tag>
                    <a-tag v-if="history.unusual_ip" color="red">新 IP</a-tag>
                  </div>
                  <div class="text-sm text-gray-500 mt-1">
                    {{ formatIpLocation(history.ip, history.location) }}
                  </div>
                  <div class="text-xs text-gray-500 mt-2 break-all">
                    {{ history.user_agent || 'unknown' }}
                  </div>
                </div>

                <div class="text-right text-xs text-gray-500 flex-shrink-0">
                  <div>登录于 {{ formatTimestampLong(history.created_at) || '暂无记录' }}</div>
                  <div class="mt-1">
                    最近活跃 {{ formatTimestampLong(history.last_active_at) || '暂无记录' }}
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
