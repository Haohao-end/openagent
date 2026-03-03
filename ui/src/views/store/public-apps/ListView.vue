<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import moment from 'moment'
import {
  getPublicApps,
  getAppCategories,
  forkPublicApp,
  likeApp,
  favoriteApp,
  type PublicApp,
  type AppCategory
} from '@/services/public-app'
import { getErrorMessage } from '@/utils/error'

// 1.定义页面所需数据
const router = useRouter()
const loading = ref(false)
const apps = ref<PublicApp[]>([])
const categories = ref<AppCategory[]>([])
const category = ref('all')
type AppSortBy = 'most_liked' | 'most_favorited' | 'most_forked' | 'latest'
const sortBy = ref<AppSortBy>('most_liked')
const searchWord = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 2.排序选项
const sortOptions: Array<{ label: string; value: AppSortBy }> = [
  { label: '最多点赞', value: 'most_liked' },
  { label: '最多收藏', value: 'most_favorited' },
  { label: '最多Fork', value: 'most_forked' },
  { label: '最新发布', value: 'latest' }
]

// 3.加载应用列表
const loadApps = async () => {
  loading.value = true
  try {
    const res = await getPublicApps({
      current_page: page.value,
      page_size: pageSize.value,
      category: category.value,
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

// 4.加载分类列表
const loadCategories = async () => {
  try {
    const res = await getAppCategories()
    categories.value = res.data.categories
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '加载分类列表失败'))
  }
}

// 5.Fork应用
const handleFork = async (app: PublicApp) => {
  try {
    const res = await forkPublicApp(app.id)
    Message.success(`已Fork到个人空间: ${res.data.name}`)
    // 刷新列表以更新Fork计数
    await loadApps()
    // 跳转到个人空间
    router.push({ name: 'space-apps-detail', params: { app_id: res.data.id } })
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '操作失败'))
  }
}

// 6.点赞应用
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

// 7.收藏应用
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

// 8.分类切换
const handleCategoryChange = (newCategory: string) => {
  category.value = newCategory
  page.value = 1
  loadApps()
}

// 9.排序切换
const handleSortChange = (newSort: AppSortBy) => {
  sortBy.value = newSort
  page.value = 1
  loadApps()
}

// 10.搜索
const handleSearch = () => {
  page.value = 1
  loadApps()
}

// 11.分页变化
const handlePageChange = (newPage: number) => {
  page.value = newPage
  loadApps()
}

// 12.页面加载
onMounted(() => {
  loadCategories()
  loadApps()
})
</script>

<template>
  <a-spin :loading="loading" class="block h-full w-full">
    <div class="p-6 flex flex-col h-full">
      <!-- 顶层标题 -->
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-2">
          <a-avatar :size="32" class="bg-blue-700">
            <icon-apps :size="18" />
          </a-avatar>
          <div class="text-lg font-medium text-gray-900">应用广场</div>
        </div>
      </div>

      <!-- 筛选和排序 - 两行布局 -->
      <div class="flex flex-col gap-4 mb-6">
        <!-- 第一行：分类标签 -->
        <div class="flex items-center gap-2 overflow-x-auto scrollbar-hide pb-1">
          <a
            class="rounded-lg text-gray-700 px-3 h-8 leading-8 hover:bg-gray-200 transition-all cursor-pointer whitespace-nowrap"
            :class="{ 'bg-gray-100': category === 'all' }"
            @click="handleCategoryChange('all')"
          >
            全部
          </a>
          <a
            v-for="cat in categories"
            :key="cat.value"
            class="rounded-lg text-gray-700 px-3 h-8 leading-8 hover:bg-gray-200 transition-all cursor-pointer whitespace-nowrap"
            :class="{ 'bg-gray-100': category === cat.value }"
            @click="handleCategoryChange(cat.value)"
          >
            {{ cat.label }}
          </a>
        </div>

        <!-- 第二行：排序和搜索 -->
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <!-- 左侧排序选项 - 使用不同的样式以区分 -->
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

          <!-- 右侧搜索框 -->
          <a-input-search
            v-model="searchWord"
            placeholder="搜索应用"
            class="w-full sm:w-[240px] bg-white rounded-lg border-gray-300"
            @search="handleSearch"
          />
        </div>
      </div>

      <!-- 应用列表 -->
      <div class="flex-1 overflow-auto scrollbar-hide">
        <a-row :gutter="[20, 20]">
          <a-col v-for="app in apps" :key="app.id" :span="6">
            <a-card hoverable class="h-full">
              <button type="button" class="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg" @click="handlePreview(app)">
                <!-- 应用头部 -->
                <div class="flex items-start gap-3 mb-3">
                  <a-avatar :size="48" shape="square">
                    <img :src="app.icon" :alt="app.name" />
                  </a-avatar>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <div class="text-base font-bold text-gray-900 truncate">{{ app.name }}</div>
                    </div>
                    <a-tag size="small" class="mt-1">{{ categories.find(c => c.value === app.category)?.label || app.category }}</a-tag>
                  </div>
                </div>
                <!-- 应用描述 -->
                <div class="text-sm text-gray-600 h-[60px] line-clamp-3 mb-3">
                  {{ app.description }}
                </div>

                <!-- 统计信息 -->
                <div class="flex items-center gap-4 text-xs text-gray-500 mb-3">
                  <span class="flex items-center gap-1">
                    <icon-heart />
                    {{ app.like_count }}
                  </span>
                  <span class="flex items-center gap-1">
                    <icon-star />
                    {{ app.favorite_count }}
                  </span>
                  <span class="flex items-center gap-1">
                    <icon-branch />
                    {{ app.fork_count }}
                  </span>
                </div>

                <!-- 发布者和发布时间 -->
                <div class="text-xs text-gray-400">
                  {{ app.creator_name }} · 发布于 {{ moment(app.published_at * 1000).format('YYYY-MM-DD HH:mm') }}
                </div>
              </button>

              <!-- 操作按钮 - 顺序：点赞、收藏、Fork（所有应用统一样式） -->
              <div class="flex items-center gap-2 mb-3" @click.stop>
                <!-- 点赞按钮 -->
                <a-button
                  :type="app.is_liked ? 'primary' : 'outline'"
                  size="small"
                  @click="handleLike(app)"
                >
                  <template #icon><icon-heart :fill="app.is_liked" /></template>
                </a-button>

                <!-- 收藏按钮 -->
                <a-button
                  :type="app.is_favorited ? 'primary' : 'outline'"
                  size="small"
                  @click="handleFavorite(app)"
                >
                  <template #icon><icon-star :fill="app.is_favorited" /></template>
                </a-button>

                <!-- Fork按钮（所有应用统一显示Fork） -->
                <a-button
                  type="primary"
                  size="small"
                  @click="handleFork(app)"
                >
                  <template #icon><icon-branch /></template>
                  Fork
                </a-button>
              </div>

            </a-card>
          </a-col>

          <!-- 空状态 -->
          <a-col v-if="apps.length === 0" :span="24">
            <a-empty description="暂无应用" class="py-20" />
          </a-col>
        </a-row>
      </div>

      <!-- 分页 -->
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
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.scrollbar-hide {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.scrollbar-hide::-webkit-scrollbar {
  display: none; /* Chrome, Safari, Opera */
}
</style>
