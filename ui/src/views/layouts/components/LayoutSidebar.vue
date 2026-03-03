<script setup lang="ts">
import type { RecentConversation } from '@/models/conversation'
import { useDeleteConversation, useGetRecentConversations } from '@/hooks/use-conversation'
import { useCredentialStore } from '@/stores/credential'
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

// 1.定义自定义组件所需数据
const route = useRoute()
const router = useRouter()
const credentialStore = useCredentialStore()
const isLoggedIn = computed(() => {
  const now = Math.floor(Date.now() / 1000)
  return Boolean(
    credentialStore.credential.access_token &&
    credentialStore.credential.expire_at &&
    credentialStore.credential.expire_at > now,
  )
})
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
    recentConversations.value = recentConversations.value.filter((item) => item.id !== conversation.id)

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
  <div class="flex flex-col h-full min-h-0">
    <div class="flex flex-col gap-2">
      <router-link
        to="/home"
        :class="`flex items-center gap-2 h-8 leading-8 rounded-lg transition-all px-2 text-gray-700 hover:text-gray-900 hover:bg-gray-200 ${isHomeRootRoute ? 'bg-gray-100' : ''}`"
      >
        <icon-home-full v-if="isHomeRootRoute" />
        <icon-home v-else />
        主页
      </router-link>
      <router-link
        to="/space/apps"
        :class="`flex items-center gap-2 h-8 leading-8 rounded-lg transition-all px-2 text-gray-700 hover:text-gray-900 hover:bg-gray-200 ${route.path.startsWith('/space') ? 'bg-gray-100' : ''}`"
      >
        <icon-space-full v-if="route.path.startsWith('/space')" />
        <icon-space v-else />
        个人空间
      </router-link>
      <div class="text-gray-500 text-sm px-2">探索</div>
      <router-link
        to="/store/public-apps"
        :class="`flex items-center gap-2 h-8 leading-8 rounded-lg transition-all px-2 text-gray-700 hover:text-gray-900 hover:bg-gray-200 ${route.path.startsWith('/store/public-apps') ? 'bg-gray-100' : ''}`"
      >
        <icon-apps-full v-if="route.path.startsWith('/store/public-apps')" />
        <icon-apps v-else />
        应用广场
      </router-link>
      <router-link
        to="/store/tools"
        class="flex items-center gap-2 h-8 leading-8 rounded-lg transition-all px-2 text-gray-700 hover:text-gray-900 hover:bg-gray-200"
        active-class="bg-gray-100"
      >
        <icon-tool-full v-if="route.path.startsWith('/store/tools')" />
        <icon-tool v-else />
        插件广场
      </router-link>
      <router-link
        to="/store/workflows"
        class="flex items-center gap-2 h-8 leading-8 rounded-lg transition-all px-2 text-gray-700 hover:text-gray-900 hover:bg-gray-200"
        active-class="bg-gray-100"
      >
        <icon-storage-full v-if="route.path.startsWith('/store/workflows')" />
        <icon-storage v-else />
        工作流广场
      </router-link>
      <router-link
        to="/openapi"
        class="flex items-center gap-2 h-8 leading-8 rounded-lg transition-all px-2 text-gray-700 hover:text-gray-900 hover:bg-gray-200"
        active-class="bg-gray-100"
      >
        <icon-open-api-full v-if="route.path.startsWith('/openapi')" />
        <icon-open-api v-else />
        开放 API
      </router-link>
    </div>
    <div v-if="isLoggedIn" class="mt-1 pt-3 flex flex-col flex-1 min-h-0">
      <div class="flex items-center gap-2 px-2 mb-2">
        <div class="text-sm font-bold text-gray-700">最近对话</div>
        <div class="flex-1 h-px bg-gray-200"></div>
      </div>
      <a-skeleton :loading="getRecentConversationsLoading" animation class="px-2">
        <a-skeleton-line :rows="3" :line-height="24" :line-spacing="8" />
      </a-skeleton>
      <div
        v-if="!getRecentConversationsLoading"
        class="flex-1 min-h-0 overflow-y-auto pr-1 recent-conversation-list"
      >
        <div v-if="recentConversations.length === 0" class="text-xs text-gray-400 px-2 py-1">
          暂无最近对话
        </div>
        <div v-else class="flex flex-col gap-1">
          <div
            v-for="conversation in recentConversations"
            :key="conversation.id"
            :class="`group flex items-center gap-1 h-8 leading-8 pl-2 pr-1 text-gray-700 rounded-lg cursor-pointer ${isConversationActive(conversation) ? 'bg-blue-50 !text-blue-700' : ''} hover:bg-blue-50 hover:text-blue-700`"
            @click="() => changeConversation(conversation)"
          >
            <div class="flex-1 min-w-0 flex items-center gap-1.5">
              <icon-message
                v-if="conversation.source_type === 'assistant_agent'"
                class="text-gray-400 group-hover:text-current"
              />
              <icon-apps
                v-else
                class="text-gray-400 group-hover:text-current"
              />
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
                <a-doption class="text-red-700" @click.stop="() => deleteRecentConversation(conversation)">
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
