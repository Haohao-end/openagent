<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import storage from '@/utils/storage'
import { useRoute, useRouter } from 'vue-router'
import { useCredentialStore } from '@/stores/credential'
import { AUTH_REQUIRED_EVENT } from '@/utils/request'

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
const unauthDescription = computed(() => {
  if (route.path.startsWith('/space/apps')) return '请你登录查看你的Agent！'
  if (route.path.startsWith('/space/tools')) return '请你登录查看你的插件！'
  if (route.path.startsWith('/space/workflows')) return '请你登录查看你的工作流！'
  if (route.path.startsWith('/space/datasets')) return '请你登录查看你的知识库！'
  return '请你登录查看你的个人空间内容！'
})
const createType = ref<string>('')
const pendingCreateType = ref<string>('')
const searchWord = ref(String(route.query?.search_word ?? ''))
const SPACE_APPS_SEARCH_DRAFT_STORAGE_KEY = 'draft:space-apps:search-word'

const openLoginModal = () => {
  if (typeof window === 'undefined') return
  window.dispatchEvent(
    new CustomEvent(AUTH_REQUIRED_EVENT, {
      detail: { redirect: route.fullPath },
    }),
  )
}

const handleCreate = (type: 'app' | 'tool' | 'workflow' | 'dataset') => {
  if (isLoggedIn.value) {
    createType.value = type
    return
  }
  pendingCreateType.value = type
  openLoginModal()
}

const persistSpaceAppsSearchWord = (value: string) => {
  if (value.trim() === '') {
    storage.remove(SPACE_APPS_SEARCH_DRAFT_STORAGE_KEY)
    return
  }
  storage.set(SPACE_APPS_SEARCH_DRAFT_STORAGE_KEY, value)
}

const getSpaceAppsSearchWordDraft = () => {
  return String(storage.get(SPACE_APPS_SEARCH_DRAFT_STORAGE_KEY, ''))
}

// 绑定输入框的搜索事件
const search = (value: string) => {
  router.push({
    path: route.path,
    query: {
      search_word: value,
    },
  })
}

// 监听路由里的search_word变化
watch(
  [() => route.path, () => route.query?.search_word],
  ([path, routeSearchWord]) => {
    if (path.startsWith('/space/apps') && !routeSearchWord) {
      searchWord.value = getSpaceAppsSearchWordDraft()
      return
    }
    searchWord.value = String(routeSearchWord ?? '')
  },
  { immediate: true },
)

watch(searchWord, (value) => {
  if (!route.path.startsWith('/space/apps')) return
  persistSpaceAppsSearchWord(value)
})

watch(
  isLoggedIn,
  async (loggedIn) => {
    if (!loggedIn || !pendingCreateType.value) return
    const targetCreateType = pendingCreateType.value
    pendingCreateType.value = ''
    createType.value = ''
    await nextTick()
    createType.value = targetCreateType
  },
  { immediate: true },
)
</script>

<template>
  <!-- 调整边距+隐藏 -->
  <div class="px-6 flex flex-col overflow-auto h-full">
    <div class="pt-6 sticky top-0 z-20 bg-gray-50">
      <!-- 顶层标题+创建按钮 -->
      <div class="flex items-center justify-between mb-6 flex-wrap gap-2">
        <!-- 左侧标题 -->
        <div class="flex items-center gap-2">
          <a-avatar :size="32" class="bg-blue-700">
            <icon-user :size="18" />
          </a-avatar>
          <div class="text-lg font-medium text-gray-900">个人空间</div>
        </div>
        <!-- 创建按钮 -->
        <a-button
          v-if="route.path.startsWith('/space/apps')"
          type="primary"
          class="rounded-lg"
          @click="handleCreate('app')"
        >
          创建 AI 应用
        </a-button>
        <a-button
          v-if="route.path.startsWith('/space/tools')"
          type="primary"
          class="rounded-lg"
          @click="handleCreate('tool')"
        >
          创建自定义插件
        </a-button>
        <a-button
          v-if="route.path.startsWith('/space/workflows')"
          type="primary"
          class="rounded-lg"
          @click="handleCreate('workflow')"
        >
          创建工作流
        </a-button>
        <a-button
          v-if="route.path.startsWith('/space/datasets')"
          type="primary"
          class="rounded-lg"
          @click="handleCreate('dataset')"
        >
          创建知识库
        </a-button>
      </div>
      <!-- 导航按钮+搜索框 -->
      <div class="flex items-center justify-between mb-6 flex-wrap gap-2">
        <!-- 左侧导航 -->
        <div class="flex items-center gap-2">
          <router-link
            to="/space/apps"
            class="rounded-lg text-gray-700 px-3 h-8 leading-8 hover:bg-gray-200 transition-all"
            active-class="bg-gray-100"
          >
            AI应用
          </router-link>
          <router-link
            to="/space/tools"
            class="rounded-lg text-gray-700 px-3 h-8 leading-8 hover:bg-gray-200 transition-all"
            active-class="bg-gray-100"
          >
            插件
          </router-link>
          <router-link
            to="/space/workflows"
            class="rounded-lg text-gray-700 px-3 h-8 leading-8 hover:bg-gray-200 transition-all"
            active-class="bg-gray-100"
          >
            工作流
          </router-link>
          <router-link
            to="/space/datasets"
            class="rounded-lg text-gray-700 px-3 h-8 leading-8 hover:bg-gray-200 transition-all"
            active-class="bg-gray-100"
          >
            知识库
          </router-link>
        </div>
        <!-- 右侧搜索 -->
        <a-input-search
          v-model="searchWord"
          :disabled="!isLoggedIn"
          placeholder="输入关键词进行搜索"
          class="w-[240px] bg-white rounded-lg border-gray-300"
          @search="search"
        />
      </div>
    </div>
    <!-- 中间内容 -->
    <router-view v-if="isLoggedIn" v-model:create-type="createType" />
    <div v-else class="flex-1 flex items-center justify-center">
      <a-empty :description="unauthDescription" />
    </div>
  </div>
</template>

<style scoped></style>
