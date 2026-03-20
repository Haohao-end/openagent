<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useLogout } from '@/hooks/use-auth'
import LayoutSidebar from './components/LayoutSidebar.vue'
import RecentConversationsGlobalPopover from './components/RecentConversationsGlobalPopover.vue'
import { useGetCurrentUser } from '@/hooks/use-account'
import { useCredentialStore } from '@/stores/credential'
import { useAccountStore } from '@/stores/account'
import SettingModal from '@/views/layouts/components/SettingModal.vue'
import LoginModal from '@/views/auth/components/LoginModal.vue'
import { AUTH_REQUIRED_EVENT } from '@/utils/request'
import IconOpenAgent from '@/components/icons/IconOpenAgent.vue'
import { useRoute } from 'vue-router'
import { getUserAvatarUrl } from '@/utils/helper'
import AgentNotification from '@/components/AgentNotification.vue'
import { setupAgentNotificationListener } from '@/services/websocket'

// 1.定义页面所需数据
const settingModalVisible = ref(false)
const loginModalVisible = ref(false)
const loginRedirectPath = ref('')
const sidebarCollapsed = ref(false)
const popoverVisible = ref(false)
const popoverData = ref<any>(null)
const popoverPosition = ref({ top: 0, left: 0 })
const agentNotificationRef = ref()
const RECENT_CONVERSATIONS_POPOVER_MARGIN = 12
const router = useRouter()
const route = useRoute()
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
const sidebarWidth = computed(() => (sidebarCollapsed.value ? 80 : 240))
const isSearchActive = computed(() => route.path === '/search')

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

const clamp = (value: number, min: number, max: number) => {
  if (max < min) return min
  return Math.min(Math.max(value, min), max)
}

const adjustRecentConversationsPopoverPosition = async () => {
  if (typeof window === 'undefined' || !popoverVisible.value) return

  await nextTick()

  const popoverElement = document.getElementById('recent-conversations-popover')
  if (!popoverElement) return

  const { innerWidth, innerHeight } = window
  const { width, height } = popoverElement.getBoundingClientRect()

  popoverPosition.value = {
    top: clamp(
      popoverPosition.value.top,
      RECENT_CONVERSATIONS_POPOVER_MARGIN,
      innerHeight - height - RECENT_CONVERSATIONS_POPOVER_MARGIN,
    ),
    left: clamp(
      popoverPosition.value.left,
      RECENT_CONVERSATIONS_POPOVER_MARGIN,
      innerWidth - width - RECENT_CONVERSATIONS_POPOVER_MARGIN,
    ),
  }
}

const handleRecentConversationsShow = (event: Event) => {
  const customEvent = event as CustomEvent<any>
  const detail = customEvent.detail
  const rect = detail.triggerRect

  popoverPosition.value = {
    top: rect.top,
    left: rect.right + RECENT_CONVERSATIONS_POPOVER_MARGIN,
  }

  popoverData.value = {
    conversations: detail.conversations,
    loading: detail.loading,
  }
  popoverVisible.value = true

  void adjustRecentConversationsPopoverPosition()
}

const handleRecentConversationsHide = () => {
  popoverVisible.value = false
}

const handleViewportResize = () => {
  void adjustRecentConversationsPopoverPosition()
}

onMounted(() => {
  if (typeof window === 'undefined') return
  window.addEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired as EventListener)
  window.addEventListener('recent-conversations:show', handleRecentConversationsShow)
  window.addEventListener('recent-conversations:hide', handleRecentConversationsHide)
  window.addEventListener('resize', handleViewportResize)
  setupAgentNotificationListener(agentNotificationRef)
})

onUnmounted(() => {
  if (typeof window === 'undefined') return
  window.removeEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired as EventListener)
  window.removeEventListener('recent-conversations:show', handleRecentConversationsShow)
  window.removeEventListener('recent-conversations:hide', handleRecentConversationsHide)
  window.removeEventListener('resize', handleViewportResize)
})
</script>

<template>
  <div class="h-full w-full overflow-hidden flex">
    <!-- 侧边栏 - 固定定位，不随右侧滚动 -->
    <a-layout-sider
      class="bg-gray-50 p-2 shadow-none flex-shrink-0 overflow-hidden sidebar-sider"
      :style="{ width: `${sidebarWidth}px`, minWidth: `${sidebarWidth}px`, maxWidth: `${sidebarWidth}px`, position: 'fixed', left: 0, top: 0, bottom: 0, height: '100vh', zIndex: 10 }"
    >
      <div class="bg-white rounded-lg px-2 py-1 flex flex-col min-h-0 overflow-hidden" style="height: calc(100vh - 16px)">
        <!-- 顶部 Logo 和折叠按钮 -->
        <div class="flex-shrink-0 flex items-center justify-center">
          <div v-if="!sidebarCollapsed" class="h-10 flex items-end justify-between w-full gap-0.5 pb-0">
            <div class="flex items-center justify-start flex-1 min-w-0 overflow-hidden">
              <icon-open-agent type="character" :size="130" class="flex-shrink-0" />
            </div>
            <!-- 搜索按钮 - 展开时在折叠按钮左侧 -->
            <router-link
              to="/search"
              :class="`p-0.5 rounded-lg transition-colors flex-shrink-0 flex items-center justify-center h-7 w-7 ${isSearchActive ? 'bg-blue-50 text-blue-700 hover:bg-blue-100' : 'text-gray-600 hover:bg-gray-100'}`"
              :title="isSearchActive ? '历史对话' : ''"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </router-link>
            <button
              @click="sidebarCollapsed = !sidebarCollapsed"
              class="p-0.5 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0 flex items-center justify-center h-7 w-7"
              :title="sidebarCollapsed ? '展开' : '折叠'"
            >
              <svg
                class="w-4 h-4 text-gray-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </button>
          </div>
          <div v-else class="flex flex-col items-center justify-center gap-0.5 py-0.5">
            <div class="flex items-center justify-center w-10 h-10 flex-shrink-0">
              <icon-open-agent type="full" :size="32" class="flex-shrink-0" />
            </div>
            <!-- 折叠时所有按钮在同一垂直线上 -->
            <button
              @click="sidebarCollapsed = !sidebarCollapsed"
              class="p-0.5 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0 flex items-center justify-center h-7 w-7"
              :title="sidebarCollapsed ? '展开' : '折叠'"
            >
              <svg
                class="w-3.5 h-3.5 text-gray-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
            </button>
            <!-- 搜索按钮 - 折叠时显示在折叠按钮下方，同一垂直线 -->
            <router-link
              to="/search"
              :class="`flex items-center justify-center h-7 w-7 rounded-lg cursor-pointer transition-all duration-200 flex-shrink-0 ${isSearchActive ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:text-gray-700 hover:bg-gray-100'}`"
              :title="isSearchActive ? '历史对话' : ''"
            >
              <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </router-link>
          </div>
        </div>
        <!-- 顶部间距 -->
        <div class="mb-3 flex-shrink-0"></div>
        <!-- 侧边栏导航 - 中间可滚动区域 -->
        <layout-sidebar class="flex-1 min-h-0 overflow-hidden" :collapsed="sidebarCollapsed" />
        <!-- 账号设置 - 固定在底部，不随滚动 -->
        <div class="h-14 flex-shrink-0 flex items-center border-t border-gray-100">
          <a-dropdown v-if="isLoggedIn" position="tl">
            <div
              class="flex items-center p-1.5 gap-2 transition-all cursor-pointer rounded-lg hover:bg-gray-100 w-full"
            >
              <!-- 头像 -->
              <a-avatar
                :size="32"
                class="flex-shrink-0 text-sm bg-blue-700"
                :image-url="getUserAvatarUrl(accountStore.account.avatar, accountStore.account.name)"
              >
                {{ accountStore.account.name[0] }}
              </a-avatar>
              <!-- 个人信息 - 使用 v-show 保持 DOM 结构 -->
              <div v-show="!sidebarCollapsed" class="flex flex-col min-w-0 flex-1">
                <div class="text-sm text-gray-900 truncate">{{ accountStore.account.name }}</div>
                <div class="text-xs text-gray-500 truncate">{{ accountStore.account.email }}</div>
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
          <div v-show="!isLoggedIn" class="p-1.5 w-full">
            <a-button long class="rounded-lg" @click="goHomeAndOpenLogin"> 登录 </a-button>
          </div>
        </div>
      </div>
    </a-layout-sider>
    <!-- 右侧内容 -->
    <a-layout-content class="!bg-transparent layout-content overflow-hidden flex flex-col" :style="{ marginLeft: `${sidebarWidth}px`, height: 'auto', flex: '1 1 0', minHeight: '0' }">
      <router-view v-slot="{ Component }">
        <keep-alive include="HomeView">
          <component :is="Component" class="flex-1 min-h-0" />
        </keep-alive>
      </router-view>
    </a-layout-content>
    <login-modal v-model:visible="loginModalVisible" @success="handleLoginSuccess" />
    <!-- 设置模态窗 -->
    <setting-modal v-model:visible="settingModalVisible" />
    <!-- Agent通知组件 -->
    <AgentNotification ref="agentNotificationRef" />
    <!-- 最近对话全局 Popover -->
    <recent-conversations-global-popover
      v-if="popoverVisible && popoverData"
      :conversations="popoverData.conversations"
      :loading="popoverData.loading"
      :style="{
        position: 'fixed',
        top: `${popoverPosition.top}px`,
        left: `${popoverPosition.left}px`,
      }"
    />
  </div>
</template>

<style scoped>
.sidebar-sider {
  transition: width 1000ms cubic-bezier(0.4, 0, 0.2, 1);
}

.layout-content {
  will-change: margin-left;
  height: auto !important;
  flex: 1 1 0 !important;
  min-height: 0 !important;
}

/* 隐藏滚条 */
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
