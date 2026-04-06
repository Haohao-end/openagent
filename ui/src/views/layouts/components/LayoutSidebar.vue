<script setup lang="ts">
import type { RecentConversation } from '@/models/conversation'
import { useDeleteConversation, useGetRecentConversations } from '@/hooks/use-conversation'
import { useCredentialStore } from '@/stores/credential'
import { isCredentialLoggedIn } from '@/utils/auth'
import UpdateConversationNameModal from '@/views/layouts/components/UpdateConversationNameModal.vue'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import IconHomeFull from '@/components/icons/IconHomeFull.vue'
import IconHome from '@/components/icons/IconHome.vue'
import IconSpaceFull from '@/components/icons/IconSpaceFull.vue'
import IconSpace from '@/components/icons/IconSpace.vue'
import IconApps from '@/components/icons/IconApps.vue'
import IconAppsFull from '@/components/icons/IconAppsFull.vue'
import IconToolFull from '@/components/icons/IconToolFull.vue'
import IconTool from '@/components/icons/IconTool.vue'
import IconStorage from '@/components/icons/IconStorage.vue'
import IconStorageFull from '@/components/icons/IconStorageFull.vue'
import IconOpenApi from '@/components/icons/IconOpenApi.vue'
import IconOpenApiFull from '@/components/icons/IconOpenApiFull.vue'

interface Props {
  collapsed?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  collapsed: false,
})
const route = useRoute()
const router = useRouter()
const credentialStore = useCredentialStore()
const isLoggedIn = computed(() => isCredentialLoggedIn(credentialStore.credential))
const selectedConversationId = computed(() => String(route.query.conversation_id || '').trim())
const isHomeRootRoute = computed(() => route.path === '/home' && !selectedConversationId.value)
const currentAppId = computed(() => {
  if (!route.path.startsWith('/space/apps/')) return ''
  return String(route.params?.app_id || '').trim()
})
const {
  loading: getRecentConversationsLoading,
  conversations: recentConversations,
  loadRecentConversations: loadRecentConversationsHook,
} = useGetRecentConversations()
const { handleDeleteConversation } = useDeleteConversation()
const updateConversationNameVisible = ref(false)
const updateConversationNameId = ref('')
const updateConversationName = ref('')

// 2.定义加载最近会话列表函数
const loadRecentConversations = async () => {
  if (!isLoggedIn.value) {
    recentConversations.value = []
    return
  }
  await loadRecentConversationsHook(20)
}

// 3.定义会话点击切换函数
const changeConversation = async (conversation: RecentConversation) => {
  if (!conversation.id) return

  if (conversation.source_type === 'assistant_agent') {
    await router.push({
      path: '/home',
      query: { conversation_id: conversation.id },
    })
    return
  }

  if (conversation.source_type === 'app_debugger' && conversation.app_id) {
    await router.push({
      path: `/space/apps/${conversation.app_id}`,
      query: {
        conversation_id: conversation.id,
        message_id: conversation.message_id,
      },
    })
  }
}

const isConversationActive = (conversation: RecentConversation) => {
  const currentConversationId = selectedConversationId.value
  if (!currentConversationId) return false
  if (currentConversationId !== conversation.id) return false

  if (route.path.startsWith('/home')) {
    return conversation.source_type === 'assistant_agent'
  }

  if (currentAppId.value) {
    return conversation.source_type === 'app_debugger' && conversation.app_id === currentAppId.value
  }

  return false
}

// 4.定义打开重命名会话弹窗函数
const openUpdateNameModal = (conversation: RecentConversation) => {
  updateConversationNameId.value = conversation.id
  updateConversationName.value = conversation.name
  updateConversationNameVisible.value = true
}

// 5.定义重命名成功回调函数
const updateConversationNameSuccess = (conversation_id: string, name: string) => {
  const idx = recentConversations.value.findIndex((item) => item.id === conversation_id)
  if (idx !== -1) {
    recentConversations.value[idx].name = name
  }
}

// 6.定义删除会话函数
const deleteRecentConversation = (conversation: RecentConversation) => {
  handleDeleteConversation(conversation.id, async () => {
    recentConversations.value = recentConversations.value.filter(
      (item) => item.id !== conversation.id,
    )

    if (selectedConversationId.value === conversation.id) {
      if (conversation.source_type === 'assistant_agent') {
        await router.replace({ path: '/home' })
      } else if (conversation.source_type === 'app_debugger' && conversation.app_id) {
        await router.replace({ path: `/space/apps/${conversation.app_id}` })
      }
    }
    await loadRecentConversations()
  })
}

const handleRecentConversationsRefresh = () => {
  void loadRecentConversations()
}

// 处理最近对话按钮 hover
const handleRecentConversationsHover = (event: MouseEvent) => {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()

  // 触发全局事件，传递按钮位置和数据
  window.dispatchEvent(
    new CustomEvent('recent-conversations:show', {
      detail: {
        conversations: recentConversations.value,
        loading: getRecentConversationsLoading.value,
        triggerRect: {
          top: rect.top,
          left: rect.left,
          right: rect.right,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height,
        },
      },
    }),
  )
}

const handleRecentConversationsLeave = () => {
  // 按钮离开时不立即隐藏，让 Popover 自己决定
}

watch(
  () => isLoggedIn.value,
  async (loggedIn) => {
    if (!loggedIn) {
      recentConversations.value = []
      return
    }
    await loadRecentConversations()
  },
  { immediate: true },
)

onMounted(() => {
  if (typeof window === 'undefined') return
  window.addEventListener('recent-conversations:refresh', handleRecentConversationsRefresh)
})

onUnmounted(() => {
  if (typeof window === 'undefined') return
  window.removeEventListener('recent-conversations:refresh', handleRecentConversationsRefresh)
})
</script>

<template>
  <div class="flex flex-col h-full min-h-0 overflow-hidden">
    <!-- 导航菜单 -->
    <div :class="`flex flex-col gap-0.5 mt-2 flex-shrink-0 ${props.collapsed ? 'items-center' : ''}`">
      <router-link
        to="/home"
        :class="`flex items-center h-9 rounded-lg transition-all text-gray-700 hover:text-gray-900 hover:bg-gray-200 flex-shrink-0 ${props.collapsed ? 'justify-center w-9' : 'gap-2 px-2'} ${isHomeRootRoute ? 'bg-gray-100' : ''}`"
        :title="isHomeRootRoute ? '主页' : ''"
      >
        <icon-home-full v-if="isHomeRootRoute" class="flex-shrink-0 w-4 h-4" />
        <icon-home v-else class="flex-shrink-0 w-4 h-4" />
        <span v-if="!props.collapsed" class="truncate text-sm">主页</span>
      </router-link>
      <router-link
        to="/space/apps"
        :class="`flex items-center h-9 rounded-lg transition-all text-gray-700 hover:text-gray-900 hover:bg-gray-200 flex-shrink-0 ${props.collapsed ? 'justify-center w-9' : 'gap-2 px-2'} ${route.path.startsWith('/space') ? 'bg-gray-100' : ''}`"
        :title="route.path.startsWith('/space') ? '个人空间' : ''"
      >
        <icon-space-full v-if="route.path.startsWith('/space')" class="flex-shrink-0 w-4 h-4" />
        <icon-space v-else class="flex-shrink-0 w-4 h-4" />
        <span v-if="!props.collapsed" class="truncate text-sm">个人空间</span>
      </router-link>
      <div v-show="!props.collapsed" class="text-gray-500 text-xs px-2 mt-1 mb-1">探索</div>
      <router-link
        to="/store/public-apps"
        :class="`flex items-center h-9 rounded-lg transition-all text-gray-700 hover:text-gray-900 hover:bg-gray-200 flex-shrink-0 ${props.collapsed ? 'justify-center w-9' : 'gap-2 px-2'} ${route.path.startsWith('/store/public-apps') ? 'bg-gray-100' : ''}`"
        :title="route.path.startsWith('/store/public-apps') ? '应用广场' : ''"
      >
        <icon-apps-full
          v-if="route.path.startsWith('/store/public-apps')"
          class="flex-shrink-0 w-4 h-4"
        />
        <icon-apps v-else class="flex-shrink-0 w-4 h-4" />
        <span v-if="!props.collapsed" class="truncate text-sm">应用广场</span>
      </router-link>
      <router-link
        to="/store/workflows"
        :class="`flex items-center h-9 rounded-lg transition-all text-gray-700 hover:text-gray-900 hover:bg-gray-200 flex-shrink-0 ${props.collapsed ? 'justify-center w-9' : 'gap-2 px-2'} ${route.path.startsWith('/store/workflows') ? 'bg-gray-100' : ''}`"
        active-class="bg-gray-100"
        :title="route.path.startsWith('/store/workflows') ? '工作流广场' : ''"
      >
        <icon-storage-full
          v-if="route.path.startsWith('/store/workflows')"
          class="flex-shrink-0 w-4 h-4"
        />
        <icon-storage v-else class="flex-shrink-0 w-4 h-4" />
        <span v-if="!props.collapsed" class="truncate text-sm">工作流广场</span>
      </router-link>
      <router-link
        to="/store/tools"
        :class="`flex items-center h-9 rounded-lg transition-all text-gray-700 hover:text-gray-900 hover:bg-gray-200 flex-shrink-0 ${props.collapsed ? 'justify-center w-9' : 'gap-2 px-2'} ${route.path.startsWith('/store/tools') ? 'bg-gray-100' : ''}`"
        active-class="bg-gray-100"
        :title="route.path.startsWith('/store/tools') ? '插件广场' : ''"
      >
        <icon-tool-full
          v-if="route.path.startsWith('/store/tools')"
          class="flex-shrink-0 w-4 h-4"
        />
        <icon-tool v-else class="flex-shrink-0 w-4 h-4" />
        <span v-if="!props.collapsed" class="truncate text-sm">插件广场</span>
      </router-link>
      <router-link
        to="/openapi"
        :class="`flex items-center h-9 rounded-lg transition-all text-gray-700 hover:text-gray-900 hover:bg-gray-200 flex-shrink-0 ${props.collapsed ? 'justify-center w-9' : 'gap-2 px-2'} ${route.path.startsWith('/openapi') ? 'bg-gray-100' : ''}`"
        active-class="bg-gray-100"
        :title="route.path.startsWith('/openapi') ? '开放 API' : ''"
      >
        <icon-open-api-full
          v-if="route.path.startsWith('/openapi')"
          class="flex-shrink-0 w-4 h-4"
        />
        <icon-open-api v-else class="flex-shrink-0 w-4 h-4" />
        <span v-if="!props.collapsed" class="truncate text-sm">开放 API</span>
      </router-link>
    </div>

    <!-- 最近对话区域 - 可滚动 -->
    <div v-if="isLoggedIn" class="flex flex-col flex-1 min-h-0 overflow-hidden">
      <!-- 侧边栏展开时显示完整列表 -->
      <div v-if="!props.collapsed" class="mt-2 pt-2 flex items-center gap-2 px-2 mb-1 flex-shrink-0">
        <router-link
          to="/search"
          :class="`text-sm font-bold cursor-pointer transition-colors ${route.path === '/search' ? 'text-blue-700' : 'text-gray-700 hover:text-blue-700'}`"
        >
          最近对话
        </router-link>
        <div class="flex-1 h-px bg-gray-200"></div>
      </div>

      <!-- 加载骨架屏 -->
      <a-skeleton
        v-if="!props.collapsed"
        :loading="getRecentConversationsLoading"
        animation
        class="px-2 flex-shrink-0"
      >
        <a-skeleton-line :rows="3" :line-height="24" :line-spacing="8" />
      </a-skeleton>

      <!-- 最近对话列表 - 只在展开时显示，固定高度可滚动 -->
      <div
        v-if="!props.collapsed"
        class="flex-1 min-h-0 overflow-y-auto pr-1 recent-conversation-list"
      >
        <div v-if="recentConversations.length === 0" class="text-xs text-gray-400 px-2 py-1">
          暂无最近对话
        </div>
        <div v-else class="flex flex-col gap-0.5">
          <div
            v-for="conversation in recentConversations"
            :key="conversation.id"
            :class="`group flex items-center gap-1 h-8 leading-8 pl-2 pr-1 text-gray-700 rounded-lg cursor-pointer ${isConversationActive(conversation) ? 'bg-blue-50 !text-blue-700' : ''} hover:bg-blue-50 hover:text-blue-700`"
            @click="() => changeConversation(conversation)"
          >
            <div class="flex-1 min-w-0 flex items-center gap-1.5">
              <icon-message
                v-if="conversation.source_type === 'assistant_agent'"
                class="text-gray-400 group-hover:text-current flex-shrink-0"
              />
              <icon-apps v-else class="text-gray-400 group-hover:text-current flex-shrink-0" />
              <div class="flex-1 line-clamp-1 break-all">{{ conversation.name }}</div>
            </div>
            <a-dropdown position="br">
              <a-button
                size="mini"
                type="text"
                class="!text-inherit !bg-transparent invisible group-hover:visible"
                @click.stop
              >
                <template #icon>
                  <icon-more />
                </template>
              </a-button>
              <template #content>
                <a-doption @click.stop="() => openUpdateNameModal(conversation)">
                  <template #icon>
                    <icon-edit />
                  </template>
                  重命名
                </a-doption>
                <a-doption
                  class="text-red-700"
                  @click.stop="() => deleteRecentConversation(conversation)"
                >
                  <template #icon>
                    <icon-delete />
                  </template>
                  删除会话
                </a-doption>
              </template>
            </a-dropdown>
          </div>
        </div>
      </div>

      <!-- 侧边栏收缩时显示按钮组 - 最近对话按钮与搜索按钮和折叠按钮保持相同间距 -->
      <div v-if="props.collapsed" class="flex flex-col gap-0.5 items-center px-2 flex-shrink-0 mt-2">
        <!-- 最近对话按钮 -->
        <div
          class="flex items-center justify-center w-7 h-7 rounded-lg cursor-pointer transition-all duration-200 text-blue-600 hover:text-blue-700 hover:bg-blue-50 group flex-shrink-0"
          @mouseenter="handleRecentConversationsHover"
          @mouseleave="handleRecentConversationsLeave"
          :title="`最近对话 (${recentConversations.length})`"
        >
          <div class="relative w-4 h-4 flex items-center justify-center flex-shrink-0">
            <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <!-- 数量徽章 - 只在 hover 时显示 -->
            <div
              v-if="recentConversations.length > 0"
              class="absolute -top-2 -right-2 min-w-5 h-5 bg-blue-200 text-blue-700 text-xs rounded-full flex items-center justify-center font-bold px-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex-shrink-0"
            >
              {{ recentConversations.length }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <update-conversation-name-modal
      v-model:visible="updateConversationNameVisible"
      :conversation_id="updateConversationNameId"
      :conversation_name="updateConversationName"
      @saved="updateConversationNameSuccess"
    />
  </div>
</template>

<style scoped>
.recent-conversation-list {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.recent-conversation-list::-webkit-scrollbar {
  width: 0;
  height: 0;
}
</style>
