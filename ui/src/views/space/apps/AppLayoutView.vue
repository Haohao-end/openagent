<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useCancelPublish, useGetApp, usePublish, useShareAppToSquare, useUnshareAppFromSquare } from '@/hooks/use-app'
import { onMounted, ref } from 'vue'
import PublishHistoryDrawer from '@/views/space/apps/components/PublishHistoryDrawer.vue'
import { formatTimestampTime } from '@/utils/time-formatter'

const route = useRoute()
const publishHistoryDrawerVisible = ref(false)
const { loading, app, loadApp } = useGetApp()
const { loading: publishLoading, handlePublish } = usePublish()
const { handleCancelPublish } = useCancelPublish()
const { loading: shareLoading, handleShareAppToSquare } = useShareAppToSquare()
const { handleUnshareAppFromSquare } = useUnshareAppFromSquare()

onMounted(async () => await loadApp(String(route.params?.app_id)))
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
        <router-link :to="{ name: 'space-apps-list' }">
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
            <div v-else class="text-gray-700 font-bold">{{ app.name }}</div>
            <div v-if="loading" class="flex items-center gap-2">
              <a-skeleton-line :widths="[60]" :line-height="18" />
              <a-skeleton-line :widths="[60]" :line-height="18" />
              <a-skeleton-line :widths="[60]" :line-height="18" />
            </div>
            <div v-else class="flex items-center gap-2">
              <div class="flex items-center h-[18px] text-xs text-gray-500">
                <icon-user />
                个人空间
              </div>
              <div class="flex items-center h-[18px] text-xs text-gray-500">
                <icon-schedule />
                {{ app.status === 'draft' ? '草稿' : '已发布' }}
              </div>
              <a-tag size="small" class="rounded h-[18px] leading-[18px] bg-gray-200 text-gray-500">
                已自动保存 {{ formatTimestampTime(app.draft_updated_at) }}
              </a-tag>
            </div>
          </div>
        </div>
      </div>
      <!-- 导航菜单 -->
      <div class="absolute left-1/2 -translate-x-1/2">
        <a-space :size="12">
          <router-link
            :to="{ name: 'space-apps-detail', params: { app_id: String(route.params?.app_id) } }"
            class="text-base font-bold text-gray-500"
            active-class="!text-blue-700"
          >
            编排
          </router-link>
          <router-link
            :to="{ name: 'space-apps-published', params: { app_id: String(route.params?.app_id) } }"
            class="text-base font-bold text-gray-500"
            active-class="!text-blue-700"
          >
            发布配置
          </router-link>
          <router-link
            :to="{ name: 'space-apps-analysis', params: { app_id: String(route.params?.app_id) } }"
            class="text-base font-bold text-gray-500"
            active-class="!text-blue-700"
          >
            统计分析
          </router-link>
        </a-space>
      </div>
      <!-- 右侧按钮信息 -->
      <div class="">
        <a-space :size="12">
          <a-button
            :disabled="loading"
            class="rounded-lg"
            @click="publishHistoryDrawerVisible = true"
          >
            <template #icon>
              <icon-schedule />
            </template>
          </a-button>
          <a-button-group>
            <a-button
              :disabled="loading"
              :loading="publishLoading || shareLoading"
              type="primary"
              class="!rounded-tl-lg !rounded-bl-lg"
              @click="
                async () => {
                  const app_id = String(route.params?.app_id)
                  await handlePublish(app_id, true)
                  await loadApp(app_id)
                }
              "
            >
              更新发布
            </a-button>
            <a-dropdown position="br">
              <a-button
                :disabled="loading"
                type="primary"
                class="!rounded-tr-lg !rounded-br-lg !w-5"
              >
                <template #icon>
                  <icon-down />
                </template>
              </a-button>
              <template #content>
                <a-doption
                  @click="
                    async () => {
                      const app_id = String(route.params?.app_id)
                      await handlePublish(app_id, false)
                      await loadApp(app_id)
                    }
                  "
                >
                  更新配置
                </a-doption>
                <a-doption
                  :disabled="app.status !== 'published'"
                  @click="
                    async () => {
                      const app_id = String(route.params?.app_id)
                      if (app.is_public) {
                        await handleUnshareAppFromSquare(app_id, async () => await loadApp(app_id))
                      } else {
                        await handleShareAppToSquare(app_id, app.category || 'general', async () => await loadApp(app_id))
                      }
                    }
                  "
                >
                  {{ app.is_public ? '取消分享到广场' : '分享到广场' }}
                </a-doption>
                <a-doption
                  :disabled="app.status === 'draft'"
                  class="!text-red-700"
                  @click="
                    async () => {
                      const app_id = String(route.params?.app_id)
                      await handleCancelPublish(app_id, async () => await loadApp(app_id))
                    }
                  "
                >
                  取消发布
                </a-doption>
              </template>
            </a-dropdown>
          </a-button-group>
        </a-space>
      </div>
    </div>
    <!-- 底部内容区 -->
    <router-view :app="app" />
    <!-- 发布历史抽屉组件 -->
    <publish-history-drawer
      :app="app"
      v-model:visible="publishHistoryDrawerVisible"
      @load-draft-app-config="() => {}"
    />
  </div>
</template>

<style scoped></style>
