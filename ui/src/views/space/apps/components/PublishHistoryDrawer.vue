<script setup lang="ts">
import { onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFallbackHistoryToDraft, useGetPublishHistoriesWithPage } from '@/hooks/use-app'
import { formatTimestampLong, formatTimestampShort } from '@/utils/time-formatter'

// 1.定义组件所需要使用的数据
const props = defineProps({
  visible: { type: Boolean, required: true },
  app: { type: Object, required: true },
})
const emits = defineEmits(['update:visible', 'loadDraftAppConfig'])
const { t } = useI18n()
const {
  loading,
  paginator,
  publishHistories,
  loadPublishHistories,
  invalidatePublishHistoryRequests,
} = useGetPublishHistoriesWithPage()
const { handleFallbackHistoryToDraft } = useFallbackHistoryToDraft()

// 2.定义滚动分页函数
const handleScroll = async (event: UIEvent) => {
  // 1.获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 2.判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (loading.value) {
      return
    }
    await loadPublishHistories(String(props.app?.id))
  }
}

// 2.监听visible属性
watch(
  () => [props.visible, props.app?.id] as const,
  async ([visible]) => {
    invalidatePublishHistoryRequests()
    publishHistories.value = []
    if (visible) await loadPublishHistories(String(props.app?.id), true)
  },
  { immediate: true },
)
onUnmounted(invalidatePublishHistoryRequests)
</script>

<template>
  <!-- 发布历史配置抽屉组件 -->
  <a-drawer
    :visible="props.visible"
    :title="t('appStudio.publishHistory.title')"
    :width="394"
    :footer="false"
    :drawer-style="{ backgroundColor: '#f9fafb' }"
    @cancel="() => emits('update:visible', false)"
  >
    <a-spin
      :loading="loading"
      class="block h-full w-full scrollbar-w-none overflow-scroll"
      @scroll="handleScroll"
    >
      <!-- 顶部的应用信息 -->
      <div class="">
        <!-- 应用基础信息 -->
        <div class="flex items-center gap-3 mb-3">
          <!-- 左侧图标 -->
          <a-avatar :size="40" shape="square" class="rounded-lg" :image-url="app?.icon" />
          <!-- 右侧信息 -->
          <div class="flex flex-col">
            <div class="text-gray-700 font-bold">{{ app?.name }}</div>
            <div class="text-xs text-gray-500">
              {{ t('appStudio.publishHistory.recentEdited', { time: formatTimestampLong(app?.draft_updated_at) }) }}
            </div>
          </div>
        </div>
        <!-- 应用描述 -->
        <div class="text-gray-500">{{ app?.description }}</div>
      </div>
      <!-- 中间分隔符 -->
      <a-divider />
      <!-- 记录总记录条数 -->
      <div class="text-gray-500 text-xs mb-[18px]">
        {{ t('appStudio.publishHistory.totalRecords', { count: paginator.total_record }) }}
      </div>
      <!-- 底部的历史列表信息 -->
      <a-card
        v-for="(publishHistory, idx) in publishHistories"
        :key="publishHistory.id"
        hoverable
        class="rounded-lg mb-4 cursor-pointer group"
      >
        <div class="flex items-center justify-between">
          <!-- 左侧版本信息 -->
          <div class="flex flex-col gap-2">
            <div class="flex items-center gap-2">
              <div class="font-bold text-gray-900">{{ t('appStudio.publishHistory.version') }}</div>
              <a-tag size="small" class="text-gray-700 rounded-lg !border !border-gray-100">
                # {{ String(publishHistory.version).padStart(3, '0') }}
              </a-tag>
              <a-tag
                v-if="idx === 0"
                size="small"
                class="text-gray-700 rounded-lg !border !border-gray-100"
              >
                {{ t('appStudio.publishHistory.currentVersion') }}
              </a-tag>
            </div>
            <div class="text-xs text-gray-500">
              {{ t('appStudio.publishHistory.publishedAt', { time: formatTimestampShort(publishHistory.created_at) }) }}
            </div>
          </div>
          <!-- 回退按钮 -->
          <a-button
            size="small"
            class="rounded-lg hidden group-hover:block"
            @click="
              async () => {
                await handleFallbackHistoryToDraft(
                  String(props.app?.id),
                  String(publishHistory.id),
                  async () => {
                    emits('update:visible', false)
                    emits('loadDraftAppConfig')
                  },
                )
              }
            "
          >
            {{ t('appStudio.publishHistory.rollback') }}
          </a-button>
        </div>
      </a-card>
      <!-- 数据加载状态 -->
      <div v-if="paginator.total_page >= 2" class="flex items-center justify-center">
        <!-- 数据加载中 -->
        <a-space v-if="loading" class="my-4">
          <a-spin />
          <div class="text-gray-400">{{ t('appStudio.publishHistory.loading') }}</div>
        </a-space>
        <!-- 数据加载完成 -->
        <div v-else-if="paginator.current_page > paginator.total_page" class="text-gray-400 my-4">
          {{ t('appStudio.publishHistory.loadedAll') }}
        </div>
      </div>
    </a-spin>
  </a-drawer>
</template>

<style scoped></style>
