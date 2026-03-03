<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useLogout } from '@/hooks/use-auth'
import LayoutSidebar from './components/LayoutSidebar.vue'
import { useGetCurrentUser } from '@/hooks/use-account'
import { useCredentialStore } from '@/stores/credential'
import { useAccountStore } from '@/stores/account'
import SettingModal from '@/views/layouts/components/SettingModal.vue'
import LoginModal from '@/views/auth/components/LoginModal.vue'
import { AUTH_REQUIRED_EVENT } from '@/utils/request'

// 1.定义页面所需数据
const settingModalVisible = ref(false)
const loginModalVisible = ref(false)
const loginRedirectPath = ref('')
const router = useRouter()
const credentialStore = useCredentialStore()
const accountStore = useAccountStore()
const { handleLogout: handleLogoutHook } = useLogout()
const { current_user, loadCurrentUser } = useGetCurrentUser()
const isLoggedIn = computed(() => {
  const now = Math.floor(Date.now() / 1000)
  return Boolean(
    credentialStore.credential.access_token &&
    credentialStore.credential.expire_at &&
    credentialStore.credential.expire_at > now,
  )
})

const openLoginModal = (redirect = '') => {
  loginRedirectPath.value = redirect
  loginModalVisible.value = true
}

const goHomeAndOpenLogin = () => {
  openLoginModal(router.currentRoute.value.fullPath)
}

const handleLoginSuccess = async () => {
  await loadCurrentUser()
  accountStore.update(current_user.value)

  const redirectPath = loginRedirectPath.value
  loginRedirectPath.value = ''
  if (redirectPath && redirectPath !== router.currentRoute.value.fullPath) {
    await router.replace(redirectPath)
  }
}

// 2.退出登录按钮
const handleLogout = async () => {
  // 2.1 发起请求退出登录
  await handleLogoutHook()

  // 2.2 清空授权凭证+账号信息
  credentialStore.clear()
  accountStore.clear()

  // 2.3 回到首页
  await router.replace({ path: '/home' })
}

// 3.登录后拉取当前账号信息
watch(
  isLoggedIn,
  async (loggedIn) => {
    if (!loggedIn) {
      accountStore.clear()
      return
    }
    await loadCurrentUser()
    accountStore.update(current_user.value)
  },
  { immediate: true },
)

const handleAuthRequired = (event: Event) => {
  if (isLoggedIn.value) return
  const customEvent = event as CustomEvent<{ redirect?: string }>
  const redirectPath = customEvent.detail?.redirect || router.currentRoute.value.fullPath
  openLoginModal(redirectPath)
}

onMounted(() => {
  if (typeof window === 'undefined') return
  window.addEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired as EventListener)
})

onUnmounted(() => {
  if (typeof window === 'undefined') return
  window.removeEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired as EventListener)
})
</script>

<template>
  <a-layout has-sider class="h-full">
    <!-- 侧边栏 -->
    <a-layout-sider :width="240" class="min-h-screen bg-gray-50 p-2 shadow-none">
      <div class="bg-white h-full rounded-lg px-2 py-4 flex flex-col min-h-0">
        <!-- 上半部分 -->
        <div class="flex flex-col flex-1 min-h-0">
          <!-- 顶部-->
          <div class="h-4 w-[110px]"></div>
          <!-- 侧边栏导航 -->
          <layout-sidebar class="flex-1 min-h-0" />
        </div>
        <!-- 账号设置 -->
        <a-dropdown v-if="isLoggedIn" position="tl">
          <div
            class="flex items-center p-2 gap-2 transition-all cursor-pointer rounded-lg hover:bg-gray-100"
          >
            <!-- 头像 -->
            <a-avatar
              :size="32"
              class="flex-shrink-0 text-sm bg-blue-700"
              :image-url="accountStore.account.avatar"
            >
              {{ accountStore.account.name[0] }}
            </a-avatar>
            <!-- 个人信息 -->
            <div class="flex flex-col">
              <div class="text-sm text-gray-900">{{ accountStore.account.name }}</div>
              <div class="text-xs text-gray-500">{{ accountStore.account.email }}</div>
            </div>
          </div>
          <template #content>
            <a-doption @click="settingModalVisible = true">
              <template #icon>
                <icon-settings />
              </template>
              账号设置
            </a-doption>
            <a-doption @click="handleLogout">
              <template #icon>
                <icon-poweroff />
              </template>
              退出登录
            </a-doption>
          </template>
        </a-dropdown>
        <div v-else class="p-2">
          <a-button long class="rounded-lg" @click="goHomeAndOpenLogin">
            <template #icon>
              <icon-user />
            </template>
            登录
          </a-button>
        </div>
      </div>
    </a-layout-sider>
    <!-- 右侧内容 -->
    <a-layout-content>
      <router-view v-slot="{ Component }">
        <keep-alive include="HomeView">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </a-layout-content>
    <login-modal v-model:visible="loginModalVisible" @success="handleLoginSuccess" />
    <!-- 设置模态窗 -->
    <setting-modal v-model:visible="settingModalVisible" />
  </a-layout>
</template>

<style scoped></style>
