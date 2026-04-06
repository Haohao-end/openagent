<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import {
  getPublicApps,
  getAppTags,
  forkPublicApp,
  likeApp,
  favoriteApp,
  type PublicApp,
  type AppTag
} from '@/services/public-app'
import { getErrorMessage } from '@/utils/error'
import { formatTimestampShort } from '@/utils/time-formatter'
import ResourceCardDescription from '@/components/ResourceCardDescription.vue'

const router = useRouter()
const loading = ref(false)
const apps = ref<PublicApp[]>([])
const tags = ref<AppTag[]>([])
const selectedTags = ref<string[]>([])
type AppSortBy = 'most_liked' | 'most_favorited' | 'most_forked' | 'latest'
const sortBy = ref<AppSortBy>('most_liked')
const searchWord = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const sortOptions: Array<{ label: string; value: AppSortBy }> = [
  { label: '最多点赞', value: 'most_liked' },
  { label: '最多收藏', value: 'most_favorited' },
  { label: '最多Fork', value: 'most_forked' },
  { label: '最新发布', value: 'latest' }
]

const loadApps = async () => {
  loading.value = true
  try {
    const res = await getPublicApps({
      current_page: page.value,
      page_size: pageSize.value,
      tags: selectedTags.value.join(','),
      sort_by: sortBy.value,
      search_word: searchWord.value
    })
    apps.value = res.data.list
    total.value = res.data.paginator.total_record
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '加载应用列表失败'))
  } finally {
    loading.value = false
  }
}

const loadTags = async () => {
  try {
    const res = await getAppTags()
    tags.value = res.data.tags
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '加载标签列表失败'))
  }
}

const handleFork = async (app: PublicApp) => {
  try {
    const res = await forkPublicApp(app.id)
    Message.success(`已Fork到个人空间: ${res.data.name}`)
    await loadApps()
    router.push({ name: 'space-apps-detail', params: { app_id: res.data.id } })
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '操作失败'))
  }
}

const handleLike = async (app: PublicApp) => {
  try {
    const res = await likeApp(app.id)
    app.is_liked = res.data.is_liked
    app.like_count = res.data.like_count
    Message.success(res.data.is_liked ? '点赞成功' : '已取消点赞')
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '操作失败'))
  }
}

const handleFavorite = async (app: PublicApp) => {
  try {
    const res = await favoriteApp(app.id)
    app.is_favorited = res.data.is_favorited
    Message.success(res.data.is_favorited ? '收藏成功' : '已取消收藏')
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '操作失败'))
  }
}

const handlePreview = (app: PublicApp) => {
  router.push({ name: 'store-public-apps-preview', params: { app_id: app.id } })
}

const toggleTag = (tagId: string) => {
  const index = selectedTags.value.indexOf(tagId)
  if (index > -1) {
    selectedTags.value.splice(index, 1)
  } else {
    selectedTags.value.push(tagId)
  }
  page.value = 1
  loadApps()
}

const handleSortChange = (newSort: AppSortBy) => {
  sortBy.value = newSort
  page.value = 1
  loadApps()
}

const handleSearch = () => {
  page.value = 1
  loadApps()
}

const handlePageChange = (newPage: number) => {
  page.value = newPage
  loadApps()
}

const getDisplayTags = (appTags: string[]) => {
  if (!appTags || appTags.length === 0) return []
  return appTags.slice(0, 3)
}

const getTagName = (tagId: string) => {
  const tag = tags.value.find(t => t.id === tagId)
  return tag?.name || tagId
}

const getExtraTagCount = (appTags: string[]) => {
  if (!appTags || appTags.length <= 3) return 0
  return appTags.length - 3
}

const getExtraTagNames = (appTags: string[]) => {
  if (!appTags || appTags.length <= 3) return []
  return appTags.slice(3).map(tagId => getTagName(tagId))
}

onMounted(() => {
  loadTags()
  loadApps()
})
</script>

<template>
  <a-spin :loading="loading" class="block h-full w-full">
    <div class="p-6 flex flex-col h-full">
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-2">
          <a-avatar :size="32" class="bg-blue-700">
            <icon-apps :size="18" />
          </a-avatar>
          <div class="text-lg font-medium text-gray-900">应用广场</div>
        </div>
      </div>

      <div class="flex flex-col gap-4 mb-6">
        <div class="flex items-center gap-2 overflow-x-auto scrollbar-hide pb-1">
          <span class="text-sm text-gray-500 mr-1 whitespace-nowrap">标签:</span>
          <a
            v-for="tag in tags"
            :key="tag.id"
            class="rounded-lg px-3 h-8 leading-8 hover:bg-gray-200 transition-all cursor-pointer whitespace-nowrap text-sm"
            :class="selectedTags.includes(tag.id) ? 'bg-blue-100 text-blue-700 font-medium' : 'bg-gray-100 text-gray-700'"
            @click="toggleTag(tag.id)"
          >
            {{ tag.name }}
          </a>
        </div>

        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-sm text-gray-500 mr-1">排序:</span>
            <a
              v-for="option in sortOptions"
              :key="option.value"
              class="text-sm text-gray-600 px-2 h-7 leading-7 hover:text-blue-600 transition-all cursor-pointer whitespace-nowrap"
              :class="{ 'text-blue-600 font-medium': sortBy === option.value }"
              @click="handleSortChange(option.value)"
            >
              {{ option.label }}
            </a>
          </div>

          <a-input-search
            v-model="searchWord"
            placeholder="搜索应用"
            class="w-full sm:w-[240px] bg-white rounded-lg border-gray-300"
            @search="handleSearch"
          />
        </div>
      </div>

      <div class="flex-1 overflow-auto scrollbar-hide">
        <a-row :gutter="[20, 20]">
          <a-col v-for="app in apps" :key="app.id" :span="6">
            <a-card hoverable class="h-full rounded-lg flex flex-col" :body-style="{ padding: '16px' }">
              <button type="button" class="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg flex-1" @click="handlePreview(app)">
                <!-- 顶部应用名称和标签 -->
                <div class="flex items-center gap-3 mb-3">
                  <a-avatar :size="40" shape="square" :image-url="app.icon" />
                  <div class="flex-1 min-w-0">
                    <div class="text-base font-bold text-gray-900 truncate">{{ app.name }}</div>
                    <div class="flex items-center gap-1 flex-wrap">
                      <a-tag v-for="tag in getDisplayTags(app.tags)" :key="tag" size="small">
                        {{ getTagName(tag) }}
                      </a-tag>
                      <a-tag v-if="getExtraTagCount(app.tags) > 0" size="small" class="cursor-help" :title="getExtraTagNames(app.tags).join(', ')">
                        +{{ getExtraTagCount(app.tags) }}
                      </a-tag>
                    </div>
                  </div>
                </div>

                <!-- 应用描述 -->
                <resource-card-description :text="app.description" />
              </button>

              <!-- 操作按钮 -->
              <div class="flex items-center gap-2 mt-2 mb-2">
                <button type="button" class="flex items-center gap-1.5 px-3 h-8 rounded-full transition-all duration-200 hover:scale-105" :class="app.is_liked ? 'bg-red-50' : 'bg-gray-50'" @click.stop="handleLike(app)">
                  <svg width="16" height="16" viewBox="0 0 24 24" :fill="app.is_liked ? '#ef4444' : 'none'" :stroke="app.is_liked ? 'none' : '#ef4444'" stroke-width="2">
                    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                  </svg>
                  <span :class="app.is_liked ? 'text-red-600' : 'text-gray-600'" class="text-xs font-medium">{{ app.like_count }}</span>
                </button>

                <button type="button" class="flex items-center gap-1.5 px-3 h-8 rounded-full transition-all duration-200 hover:scale-105" :class="app.is_favorited ? 'bg-yellow-50' : 'bg-gray-50'" @click.stop="handleFavorite(app)">
                  <svg width="16" height="16" viewBox="0 0 24 24" :fill="app.is_favorited ? '#eab308' : 'none'" :stroke="app.is_favorited ? 'none' : '#eab308'" stroke-width="2">
                    <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>
                  </svg>
                  <span :class="app.is_favorited ? 'text-yellow-600' : 'text-gray-600'" class="text-xs font-medium">{{ app.favorite_count }}</span>
                </button>

                <button type="button" class="flex items-center gap-1.5 px-3 h-8 rounded-full transition-all duration-200 hover:scale-105" :class="app.is_forked ? 'bg-blue-50' : 'bg-gray-50'" @click.stop="handleFork(app)">
                  <icon-branch :size="16" :style="{ color: app.is_forked ? '#3b82f6' : '#9ca3af' }" />
                  <span :class="app.is_forked ? 'text-blue-600' : 'text-gray-600'" class="text-xs font-medium">{{ app.fork_count }}</span>
                </button>
              </div>

              <!-- 发布者和发布时间 -->
              <div class="flex items-center gap-1.5">
                <a-avatar :size="18" :image-url="app.creator_avatar" />
                <div class="text-xs text-gray-400">{{ app.creator_name }} · 发布于 {{ formatTimestampShort(app.published_at) }}</div>
              </div>
            </a-card>
          </a-col>

          <a-col v-if="apps.length === 0" :span="24">
            <a-empty description="暂无应用" class="py-20" />
          </a-col>
        </a-row>
      </div>

      <div v-if="total > pageSize" class="flex justify-center mt-6">
        <a-pagination
          :current="page"
          :page-size="pageSize"
          :total="total"
          show-total
          @change="handlePageChange"
        />
      </div>
    </div>
  </a-spin>
</template>

<style scoped>
.scrollbar-hide {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
</style>
