<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getPublicAppDetail, forkPublicApp, type PublicApp } from '@/services/public-app'
import { getErrorMessage } from '@/utils/error'
import { formatTimestampShort } from '@/utils/time-formatter'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const forkLoading = ref(false)
type PreviewApp = PublicApp & { draft_updated_at: number }
const app = ref<PreviewApp>({
  id: '',
  name: '',
  icon: '',
  description: '',
  tags: [],
  view_count: 0,
  like_count: 0,
  fork_count: 0,
  favorite_count: 0,
  creator_name: '',
  creator_avatar: '',
  published_at: 0,
  created_at: 0,
  is_liked: false,
  is_favorited: false,
  draft_updated_at: 0,
})

// 加载公共应用详情
const loadApp = async () => {
  try {
    loading.value = true
    const res = await getPublicAppDetail(String(route.params?.app_id))
    // 将 draft_app_config 数据合并到 app 对象中，这样 DetailView 可以直接使用
    app.value = {
      ...res.data,
      // 添加 draft_updated_at 字段，用于显示"已自动保存"时间
      draft_updated_at: res.data.updated_at || res.data.created_at,
    }
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '加载应用失败'))
  } finally {
    loading.value = false
  }
}

// Fork 到个人空间
const handleForkToMySpace = async () => {
  try {
    forkLoading.value = true
    const res = await forkPublicApp(String(route.params?.app_id))
    Message.success(`已添加到个人空间: ${res.data.name}`)
    router.push({ name: 'space-apps-detail', params: { app_id: res.data.id } })
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '操作失败'))
  } finally {
    forkLoading.value = false
  }
}

onMounted(async () => await loadApp())
</script>

<template>
  <!-- 外层容器 -->
  <div class="min-h-screen flex flex-col h-full overflow-hidden">
    <!-- 顶部导航 -->
    <div
      class="h-[77px] flex-shrink-0 bg-gray-50 p-4 flex items-center justify-between relative border-b"
    >
      <!-- 左侧应用信息 -->
      <div class="flex items-center gap-2">
        <!-- 回退按钮 -->
        <router-link :to="{ name: 'store-public-apps-list' }">
          <a-button size="mini">
            <template #icon>
              <icon-left />
            </template>
          </a-button>
        </router-link>
        <!-- 应用容器 -->
        <div class="flex items-center gap-3">
          <!-- 应用图标 -->
          <a-avatar :size="40" shape="square" class="rounded-lg" :image-url="app.icon" />
          <!-- 应用信息 -->
          <div class="flex flex-col justify-between h-[40px]">
            <a-skeleton-line v-if="loading" :widths="[100]" />
            <div v-else class="flex items-center gap-2">
              <div class="text-gray-700 font-bold">{{ app.name }}</div>
              <a-tag color="orange" size="small">预览模式</a-tag>
            </div>
            <div v-if="loading" class="flex items-center gap-2">
              <a-skeleton-line :widths="[60]" :line-height="18" />
              <a-skeleton-line :widths="[60]" :line-height="18" />
              <a-skeleton-line :widths="[60]" :line-height="18" />
            </div>
            <div v-else class="flex items-center gap-2">
              <a-avatar :size="20" :image-url="app.creator_avatar" />
              <div class="flex items-center h-[18px] text-xs text-gray-500">
                <icon-user />
                {{ app.creator_name }}
              </div>
              <div class="flex items-center h-[18px] text-xs text-gray-500">
                <icon-eye />
                {{ app.view_count }} 次浏览
              </div>
              <div class="flex items-center h-[18px] text-xs text-gray-500">
                <icon-branch />
                {{ app.fork_count }} 次Fork
              </div>
              <a-tag size="small" class="rounded h-[18px] leading-[18px] bg-gray-200 text-gray-500">
                发布于 {{ formatTimestampShort(app.published_at) }}
              </a-tag>
            </div>
          </div>
        </div>
      </div>
      <!-- 导航菜单 -->
      <div class="absolute left-1/2 -translate-x-1/2">
        <a-space :size="12">
          <router-link
            :to="{ name: 'store-public-apps-preview', params: { app_id: String(route.params?.app_id) } }"
            class="text-base font-bold text-gray-500"
            active-class="!text-blue-700"
          >
            编排
          </router-link>
          <router-link
            :to="{ name: 'store-public-apps-analysis', params: { app_id: String(route.params?.app_id) } }"
            class="text-base font-bold text-gray-500"
            active-class="!text-blue-700"
          >
            统计分析
          </router-link>
        </a-space>
      </div>
      <!-- 右侧按钮信息 -->
      <div class="">
        <a-button
          :loading="forkLoading"
          type="primary"
          @click="handleForkToMySpace"
        >
          <template #icon>
            <icon-plus />
          </template>
          添加到我的个人空间
        </a-button>
      </div>
    </div>
    <!-- 底部内容区 -->
    <router-view :app="app" />
  </div>
</template>

<style scoped></style>
