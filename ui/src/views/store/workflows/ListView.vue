<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import moment from 'moment'
import {
  getPublicWorkflows,
  forkPublicWorkflow,
  likeWorkflow,
  favoriteWorkflow,
  type PublicWorkflow
} from '@/services/public-workflow'
import { getAppCategories, type AppCategory } from '@/services/public-app'
import { getErrorMessage } from '@/utils/error'

const router = useRouter()
const loading = ref(false)
const workflows = ref<PublicWorkflow[]>([])
const categories = ref<AppCategory[]>([])
const category = ref('all')
type WorkflowSortBy = 'most_liked' | 'most_favorited' | 'most_forked' | 'latest'
const sortBy = ref<WorkflowSortBy>('most_liked')
const searchWord = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const sortOptions: Array<{ label: string; value: WorkflowSortBy }> = [
  { label: '最多点赞', value: 'most_liked' },
  { label: '最多收藏', value: 'most_favorited' },
  { label: '最多Fork', value: 'most_forked' },
  { label: '最新发布', value: 'latest' }
]

const loadWorkflows = async () => {
  loading.value = true
  try {
    const res = await getPublicWorkflows({
      current_page: page.value,
      page_size: pageSize.value,
      category: category.value,
      sort_by: sortBy.value,
      search_word: searchWord.value
    })
    workflows.value = res.data.list
    total.value = res.data.paginator.total_record
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '加载工作流列表失败'))
  } finally {
    loading.value = false
  }
}

const loadCategories = async () => {
  try {
    const res = await getAppCategories()
    categories.value = res.data.categories
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '加载分类列表失败'))
  }
}

const handleFork = async (workflow: PublicWorkflow) => {
  try {
    const res = await forkPublicWorkflow(workflow.id)
    Message.success(`已添加到个人空间: ${res.data.name}`)
    await loadWorkflows()
    router.push({ name: 'space-workflows-detail', params: { workflow_id: res.data.id } })
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '添加失败'))
  }
}

const handlePreview = (workflow: PublicWorkflow) => {
  router.push({ name: 'store-workflows-preview', params: { workflow_id: workflow.id } })
}

const handleLike = async (workflow: PublicWorkflow) => {
  try {
    const res = await likeWorkflow(workflow.id)
    workflow.is_liked = res.data.is_liked
    workflow.like_count = res.data.like_count
    Message.success(res.data.is_liked ? '点赞成功' : '已取消点赞')
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '操作失败'))
  }
}

const handleFavorite = async (workflow: PublicWorkflow) => {
  try {
    const res = await favoriteWorkflow(workflow.id)
    workflow.is_favorited = res.data.is_favorited
    workflow.favorite_count = res.data.favorite_count || workflow.favorite_count
    Message.success(res.data.is_favorited ? '收藏成功' : '已取消收藏')
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '操作失败'))
  }
}

onMounted(() => {
  loadCategories()
  loadWorkflows()
})
</script>

<template>
  <a-spin :loading="loading" class="block h-full w-full">
    <div class="p-6 flex flex-col h-full">
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-2">
          <a-avatar :size="32" class="bg-purple-700">
            <icon-relation :size="18" />
          </a-avatar>
          <div class="text-lg font-medium text-gray-900">工作流广场</div>
        </div>
      </div>

      <!-- 筛选和排序 - 两行布局 -->
      <div class="flex flex-col gap-4 mb-6">
        <!-- 第一行：分类标签 -->
        <div class="flex items-center gap-2 overflow-x-auto scrollbar-hide pb-1">
          <a
            class="rounded-lg text-gray-700 px-3 h-8 leading-8 hover:bg-gray-200 transition-all cursor-pointer whitespace-nowrap"
            :class="{ 'bg-gray-100': category === 'all' }"
            @click="category = 'all'; page = 1; loadWorkflows()"
          >
            全部
          </a>
          <a
            v-for="cat in categories"
            :key="cat.value"
            class="rounded-lg text-gray-700 px-3 h-8 leading-8 hover:bg-gray-200 transition-all cursor-pointer whitespace-nowrap"
            :class="{ 'bg-gray-100': category === cat.value }"
            @click="category = cat.value; page = 1; loadWorkflows()"
          >
            {{ cat.label }}
          </a>
        </div>

        <!-- 第二行：排序和搜索 -->
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <!-- 左侧排序选项 - 使用文字链接样式 -->
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-sm text-gray-500 mr-1">排序:</span>
            <a
              v-for="option in sortOptions"
              :key="option.value"
              class="text-sm text-gray-600 px-2 h-7 leading-7 hover:text-blue-600 transition-all cursor-pointer whitespace-nowrap"
              :class="{ 'text-blue-600 font-medium': sortBy === option.value }"
              @click="sortBy = option.value; page = 1; loadWorkflows()"
            >
              {{ option.label }}
            </a>
          </div>

          <!-- 右侧搜索框 -->
          <a-input-search
            v-model="searchWord"
            placeholder="搜索工作流"
            class="w-full sm:w-[240px] bg-white rounded-lg border-gray-300"
            @search="page = 1; loadWorkflows()"
          />
        </div>
      </div>

      <!-- 工作流列表 -->
      <div class="flex-1 overflow-auto scrollbar-hide">
        <a-row :gutter="[20, 20]">
          <a-col v-for="workflow in workflows" :key="workflow.id" :span="6">
            <a-card hoverable class="h-full">
              <button type="button" class="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg" @click="handlePreview(workflow)">
                <!-- 顶部图标和标题 -->
                <div class="flex items-start gap-3 mb-3">
                  <a-avatar :size="48" shape="square"><img :src="workflow.icon" :alt="workflow.name" /></a-avatar>
                  <div class="flex-1 min-w-0">
                    <div class="text-base font-bold text-gray-900 truncate">{{ workflow.name }}</div>
                    <a-tag size="small" class="mt-1">{{ categories.find(c => c.value === workflow.category)?.label || workflow.category }}</a-tag>
                  </div>
                </div>

                <!-- 描述 -->
                <div class="text-sm text-gray-600 h-[60px] line-clamp-3 mb-3">{{ workflow.description }}</div>

                <!-- 统计数据 -->
                <div class="flex items-center gap-4 text-xs text-gray-500 mb-3">
                  <span class="flex items-center gap-1">
                    <icon-heart :size="14" />
                    {{ workflow.like_count }}
                  </span>
                  <span class="flex items-center gap-1">
                    <icon-star :size="14" />
                    {{ workflow.favorite_count || 0 }}
                  </span>
                  <span class="flex items-center gap-1">
                    <icon-branch :size="14" />
                    {{ workflow.fork_count }}
                  </span>
                </div>

                <!-- 发布者和发布时间 -->
                <div class="text-xs text-gray-400">
                  {{ workflow.account_name || '匿名用户' }} · 发布于 {{ workflow.published_at > 0 ? moment(workflow.published_at * 1000).format('YYYY-MM-DD HH:mm') : '未知时间' }}
                </div>
              </button>

              <!-- 操作按钮 - 顺序：点赞、收藏、Fork -->
              <div class="flex items-center gap-2 mb-3" @click.stop>
                <!-- 点赞按钮 -->
                <a-button
                  :type="workflow.is_liked ? 'primary' : 'outline'"
                  size="small"
                  @click="handleLike(workflow)"
                >
                  <template #icon><icon-heart :fill="workflow.is_liked" /></template>
                </a-button>

                <!-- 收藏按钮 -->
                <a-button
                  :type="workflow.is_favorited ? 'primary' : 'outline'"
                  size="small"
                  @click="handleFavorite(workflow)"
                >
                  <template #icon><icon-star :fill="workflow.is_favorited" /></template>
                </a-button>

                <!-- Fork按钮 -->
                <a-button
                  type="primary"
                  size="small"
                  @click="handleFork(workflow)"
                >
                  <template #icon><icon-branch /></template>
                  Fork
                </a-button>
              </div>

            </a-card>
          </a-col>
          <a-col v-if="workflows.length === 0" :span="24"><a-empty description="暂无工作流" class="py-20" /></a-col>
        </a-row>
      </div>

      <!-- 分页 -->
      <div v-if="total > pageSize" class="flex justify-center mt-6">
        <a-pagination :current="page" :page-size="pageSize" :total="total" show-total @change="(p: number) => { page = p; loadWorkflows() }" />
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
