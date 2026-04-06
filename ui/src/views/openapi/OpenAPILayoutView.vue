<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed, ref } from 'vue'
import { useCredentialStore } from '@/stores/credential'
import { AUTH_REQUIRED_EVENT } from '@/utils/request'
import { isCredentialLoggedIn } from '@/utils/auth'

const route = useRoute()
const credentialStore = useCredentialStore()
const create_api_key = ref(false)
const isLoggedIn = computed(() => isCredentialLoggedIn(credentialStore.credential))

const openLoginModal = () => {
  if (typeof window === 'undefined') return
  window.dispatchEvent(
    new CustomEvent(AUTH_REQUIRED_EVENT, {
      detail: { redirect: route.fullPath },
    }),
  )
}

const handleCreateApiKey = () => {
  if (!isLoggedIn.value) {
    openLoginModal()
    return
  }
  create_api_key.value = true
}
</script>

<template>
  <!-- 调整边距+隐藏 -->
  <div class="px-6 flex flex-col overflow-hidden h-full">
    <div class="pt-6 sticky top-0 z-20 bg-gray-50">
      <!-- 顶层标题+创建按钮 -->
      <div class="flex items-center justify-between mb-6">
        <!-- 左侧标题 -->
        <div class="flex items-center gap-2">
          <a-avatar :size="32" class="bg-blue-700">
            <icon-link :size="18" />
          </a-avatar>
          <div class="text-lg font-medium text-gray-900">开放 API</div>
        </div>
      </div>
      <!-- 导航按钮 -->
      <div class="flex items-center justify-between mb-6">
        <!-- 左侧导航 -->
        <div class="flex items-center gap-2">
          <router-link
            to="/openapi"
            class="rounded-lg text-gray-700 px-3 h-8 leading-8 hover:bg-gray-200 transition-all"
            exact-active-class="bg-gray-100"
          >
            快速开始
          </router-link>
          <router-link
            to="/openapi/api-keys"
            class="rounded-lg text-gray-700 px-3 h-8 leading-8 hover:bg-gray-200 transition-all"
            active-class="bg-gray-100"
          >
            密钥
          </router-link>
        </div>
        <!-- 右侧按钮 -->
        <a-button
          v-if="route.path.startsWith('/openapi/api-keys')"
          type="primary"
          class="rounded-lg"
          @click="handleCreateApiKey"
        >
          新增密钥
        </a-button>
      </div>
    </div>
    <!-- 中间内容 -->
    <router-view v-model:create_api_key="create_api_key" />
  </div>
</template>

<style scoped></style>
