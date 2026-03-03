<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthorize } from '@/hooks/use-oauth'
import { useCredentialStore } from '@/stores/credential'
import { Message } from '@arco-design/web-vue'
import { getErrorMessage } from '@/utils/error'

// 1.定义页面所需的数据
const route = useRoute()
const router = useRouter()
const credentialStore = useCredentialStore()
const { authorization, handleAuthorize } = useAuthorize()
const authorizeError = ref('')
const providerName = computed(() => String(route.params?.provider_name ?? ''))

const parseAuthorizeCode = () => {
  // 1.优先取路由query中的code
  const queryCode = route.query?.code
  if (queryCode) return String(queryCode)

  // 2.兼容从URL中直接读取code参数
  const searchCode = new URLSearchParams(window.location.search).get('code')
  if (searchCode) return searchCode

  // 3.兼容少数提供商把code放在hash中的场景
  const hash = window.location.hash
  if (hash.includes('code=')) {
    const hashParams = new URLSearchParams(hash.replace(/^#/, ''))
    const hashCode = hashParams.get('code')
    if (hashCode) return hashCode
  }

  return ''
}

onMounted(async () => {
  const oauthError = String(route.query?.error ?? '')
  if (oauthError) {
    authorizeError.value = `第三方授权失败: ${oauthError}`
    Message.error(authorizeError.value)
    return
  }

  const code = parseAuthorizeCode()
  if (!code) {
    authorizeError.value = '未获取到授权码(code)，请返回登录页重试'
    Message.error(authorizeError.value)
    return
  }

  try {
    // 1.调用authorize接口进行登录
    await handleAuthorize(providerName.value, code)

    // 2.更新用户授权数据并跳转到首页
    credentialStore.update(authorization.value)
    await router.replace({ path: '/home' })
  } catch (error: unknown) {
    authorizeError.value = getErrorMessage(error, '第三方授权登录失败，请重试')
    Message.error(authorizeError.value)
  }
})
</script>

<template>
  <div class="w-full min-h-screen flex items-center justify-center bg-white">
    <div class="flex flex-col items-center gap-4">
      <a-spin v-if="!authorizeError" tip="第三方授权登录中..."></a-spin>
      <template v-else>
        <div class="text-sm text-red-500">{{ authorizeError }}</div>
        <a-button
          type="primary"
          @click="router.replace({ path: '/home', query: { login: '1', t: String(Date.now()) } })"
        >
          返回首页登录
        </a-button>
      </template>
    </div>
  </div>
</template>

<style scoped></style>
