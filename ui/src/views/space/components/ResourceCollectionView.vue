<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import type { SpaceResourceCardItem, SpaceResourceType } from '@/models/space-resource'
import { getFavorites } from '@/services/favorite'
import { getLikes } from '@/services/like'
import { favoriteApp, forkPublicApp, likeApp } from '@/services/public-app'
import { favoriteWorkflow, forkPublicWorkflow, likeWorkflow } from '@/services/public-workflow'
import { getErrorMessage } from '@/utils/error'
import { getUserAvatarUrl } from '@/utils/helper'
import { formatTimestampShort } from '@/utils/time-formatter'
import ResourceCardDescription from '@/components/ResourceCardDescription.vue'

const props = defineProps<{
  mode: 'favorites' | 'likes'
}>()

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const resourceType = ref<SpaceResourceType>('app')
const items = ref<SpaceResourceCardItem[]>([])

const isFavoritesMode = computed(() => props.mode === 'favorites')
const pageTitle = computed(() => (isFavoritesMode.value ? '我的收藏' : '我的点赞'))
const actionLabel = computed(() => (isFavoritesMode.value ? '收藏于' : '点赞于'))
const emptyDescription = computed(() => {
  if (isFavoritesMode.value) {
    return resourceType.value === 'app' ? '你还没有收藏任何应用' : '你还没有收藏任何工作流'
  }
  return resourceType.value === 'app' ? '你还没有点赞任何应用' : '你还没有点赞任何工作流'
})
const searchWord = computed(() => String(route.query.search_word ?? ''))

const typeOptions: Array<{ label: string; value: SpaceResourceType }> = [
  { label: '应用', value: 'app' },
  { label: '工作流', value: 'workflow' },
]

const loadItems = async () => {
  loading.value = true
  try {
    const requestParams = {
      search_word: searchWord.value,
      resource_type: resourceType.value,
    }
    const res = isFavoritesMode.value
      ? await getFavorites(requestParams)
      : await getLikes(requestParams)
    items.value = res.data
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, `加载${pageTitle.value}失败`))
  } finally {
    loading.value = false
  }
}

const removeItem = (itemId: string, resourceTypeValue: SpaceResourceType) => {
  items.value = items.value.filter(
    (item) => !(item.id === itemId && item.resource_type === resourceTypeValue),
  )
}

const getFavoriteCount = (item: SpaceResourceCardItem, nextFavorited: boolean, nextCount?: number) => {
  if (typeof nextCount === 'number') return nextCount
  return Math.max(0, item.favorite_count + (nextFavorited ? 1 : -1))
}

const handleLike = async (item: SpaceResourceCardItem) => {
  try {
    const res =
      item.resource_type === 'app' ? await likeApp(item.id) : await likeWorkflow(item.id)
    item.is_liked = res.data.is_liked
    item.like_count = res.data.like_count

    if (!res.data.is_liked && !isFavoritesMode.value) {
      removeItem(item.id, item.resource_type)
    }

    Message.success(res.data.is_liked ? '点赞成功' : '已取消点赞')
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '操作失败'))
  }
}

const handleFavorite = async (item: SpaceResourceCardItem) => {
  try {
    const res =
      item.resource_type === 'app' ? await favoriteApp(item.id) : await favoriteWorkflow(item.id)
    item.is_favorited = res.data.is_favorited
    item.favorite_count = getFavoriteCount(item, res.data.is_favorited, res.data.favorite_count)

    if (!res.data.is_favorited && isFavoritesMode.value) {
      removeItem(item.id, item.resource_type)
    }

    Message.success(res.data.is_favorited ? '收藏成功' : '已取消收藏')
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '操作失败'))
  }
}

const handleAddToSpace = async (item: SpaceResourceCardItem) => {
  if (item.is_forked) {
    Message.warning('已经添加到个人空间了')
    return
  }

  try {
    const res =
      item.resource_type === 'app' ? await forkPublicApp(item.id) : await forkPublicWorkflow(item.id)

    item.is_forked = true
    item.fork_count += 1
    Message.success(`已添加到个人空间: ${res.data.name}`)

    if (item.resource_type === 'app') {
      await router.push({ name: 'space-apps-detail', params: { app_id: res.data.id } })
      return
    }

    await router.push({ name: 'space-workflows-detail', params: { workflow_id: res.data.id } })
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '添加失败'))
  }
}

const handlePreview = (item: SpaceResourceCardItem) => {
  if (item.resource_type === 'app') {
    router.push({ name: 'store-public-apps-preview', params: { app_id: item.id } })
    return
  }

  router.push({ name: 'store-workflows-preview', params: { workflow_id: item.id } })
}

watch([searchWord, resourceType], () => {
  loadItems()
}, { immediate: true })
</script>

<template>
  <a-spin :loading="loading" class="block h-full w-full overflow-hidden">
    <div class="h-full flex flex-col overflow-hidden">
      <div class="flex flex-col items-start gap-3 mb-6">
        <div>
          <div class="text-lg font-medium text-gray-900">{{ pageTitle }}</div>
        </div>
        <div class="flex items-center gap-2 flex-wrap justify-start">
          <button
            v-for="option in typeOptions"
            :key="option.value"
            type="button"
            class="rounded-full px-3 h-8 text-sm transition-all"
            :class="
              resourceType === option.value
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-600 border border-gray-200 hover:border-blue-200 hover:text-blue-600'
            "
            @click="resourceType = option.value"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <div class="flex-1 min-h-0 overflow-y-auto overflow-x-hidden scrollbar-hide">
        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4 py-2 px-1">
          <a-card
            v-for="item in items"
            :key="`${item.resource_type}-${item.id}`"
            class="resource-card"
            @click="handlePreview(item)"
          >
            <button
              type="button"
              class="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg"
            >
              <div class="flex items-start gap-3 mb-3">
                <a-avatar :size="48" shape="square" class="flex-shrink-0">
                  <img :src="item.icon" :alt="item.name" />
                </a-avatar>
                <div class="flex-1 min-w-0 overflow-hidden">
                  <div class="flex items-center gap-2 mb-1">
                    <div class="text-base font-bold text-gray-900 truncate">
                      {{ item.name }}
                    </div>
                    <a-tag
                      size="small"
                      :color="item.resource_type === 'app' ? 'arcoblue' : 'green'"
                      class="flex-shrink-0"
                    >
                      {{ item.resource_type === 'app' ? '应用' : '工作流' }}
                    </a-tag>
                  </div>
                  <div class="text-xs text-gray-400">
                    {{ actionLabel }}
                    {{ item.action_at ? formatTimestampShort(item.action_at) : '--' }}
                  </div>
                </div>
              </div>

              <resource-card-description :text="item.description" class="mb-3" />

              <div class="flex items-center gap-1.5 text-xs text-gray-400 mb-3">
                <a-avatar :size="18" class="bg-blue-700" :image-url="getUserAvatarUrl(item.creator_avatar, item.creator_name)">
                  {{ (item.creator_name || '未知用户')[0] }}
                </a-avatar>
                <span class="truncate">
                  {{ item.creator_name || '未知用户' }}
                  <template v-if="item.published_at">
                    · 发布于 {{ formatTimestampShort(item.published_at) }}
                  </template>
                </span>
              </div>
            </button>

            <div class="flex items-center justify-between border-t border-gray-100 pt-3" @click.stop>
              <div class="flex items-center gap-2">
                <a-tooltip :content="item.is_liked ? '取消点赞' : '点赞'">
                  <button
                    class="flex items-center gap-1.5 px-3 h-8 rounded-full transition-all duration-200 hover:scale-105"
                    :class="item.is_liked ? 'bg-red-50' : 'bg-gray-50'"
                    @click="handleLike(item)"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      :fill="item.is_liked ? '#ef4444' : 'none'"
                      :stroke="item.is_liked ? 'none' : '#9ca3af'"
                      stroke-width="2"
                    >
                      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                    </svg>
                    <span
                      class="text-xs font-medium"
                      :class="item.is_liked ? 'text-red-600' : 'text-gray-600'"
                    >
                      {{ item.like_count }}
                    </span>
                  </button>
                </a-tooltip>

                <a-tooltip :content="item.is_favorited ? '取消收藏' : '收藏'">
                  <button
                    class="flex items-center gap-1.5 px-3 h-8 rounded-full bg-yellow-50 transition-all duration-200 hover:scale-105"
                    @click="handleFavorite(item)"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="#eab308">
                      <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>
                    </svg>
                    <span class="text-xs font-medium text-yellow-600">
                      {{ item.favorite_count }}
                    </span>
                  </button>
                </a-tooltip>

                <a-tooltip :content="item.is_forked ? '已添加到个人空间' : '添加到个人空间'">
                  <button
                    class="flex items-center gap-1.5 px-3 h-8 rounded-full transition-all duration-200"
                    :class="
                      item.is_forked
                        ? 'bg-gray-100 cursor-not-allowed opacity-50'
                        : 'bg-blue-50 hover:bg-blue-100 hover:scale-105'
                    "
                    :disabled="item.is_forked"
                    @click="handleAddToSpace(item)"
                  >
                    <icon-branch
                      :size="16"
                      :style="{ color: item.is_forked ? '#9ca3af' : '#3b82f6' }"
                    />
                    <span
                      class="text-xs font-medium"
                      :class="item.is_forked ? 'text-gray-400' : 'text-blue-600'"
                    >
                      {{ item.fork_count }}
                    </span>
                  </button>
                </a-tooltip>
              </div>

              <div class="flex items-center gap-1.5 text-xs text-gray-400">
                <icon-eye :size="14" />
                <span class="font-medium">{{ item.view_count }}</span>
              </div>
            </div>
          </a-card>

          <div v-if="items.length === 0" class="col-span-full py-20">
            <a-empty :description="emptyDescription" />
          </div>
        </div>
      </div>
    </div>
  </a-spin>
</template>

<style scoped>
.resource-card {
  height: 100%;
  cursor: pointer;
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.resource-card:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.12), 0 4px 8px rgba(0, 0, 0, 0.08);
  border-color: rgba(0, 0, 0, 0.1);
  z-index: 50;
}

.scrollbar-hide {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

:deep(.arco-spin) {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

:deep(.arco-spin-container) {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

:deep(.arco-card-body) {
  padding: 16px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

:deep(.arco-card) {
  border-radius: 16px;
}
</style>
