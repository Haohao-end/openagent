<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import {
  getPublicWorkflows,
  forkPublicWorkflow,
  likeWorkflow,
  favoriteWorkflow,
  type PublicWorkflow
} from '@/services/public-workflow'
import { getAppTags, type AppTag } from '@/services/public-app'
import { getErrorMessage } from '@/utils/error'
import { formatTimestampShort } from '@/utils/time-formatter'

const router = useRouter()
const loading = ref(false)
const workflows = ref<PublicWorkflow[]>([])
const tags = ref<AppTag[]>([])
const selectedTags = ref<string[]>([])
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
      tags: selectedTags.value.join(','),
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

const loadTags = async () => {
  try {
    const res = await getAppTags()
    tags.value = res.data.tags
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '加载标签列表失败'))
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

const toggleTag = (tagId: string) => {
  const index = selectedTags.value.indexOf(tagId)
  if (index > -1) {
    selectedTags.value.splice(index, 1)
  } else {
    selectedTags.value.push(tagId)
  }
  page.value = 1
  loadWorkflows()
}

const handleSortChange = (newSort: WorkflowSortBy) => {
  sortBy.value = newSort
  page.value = 1
  loadWorkflows()
}

const handleSearch = () => {
  page.value = 1
  loadWorkflows()
}

const handlePageChange = (newPage: number) => {
  page.value = newPage
  loadWorkflows()
}

const getDisplayTags = (workflowTags: string[]) => {
  if (!workflowTags || workflowTags.length === 0) return []
  return workflowTags.slice(0, 3)
}

const getTagName = (tagId: string) => {
  const tag = tags.value.find(t => t.id === tagId)
  return tag?.name || tagId
}

const getExtraTagCount = (workflowTags: string[]) => {
  if (!workflowTags || workflowTags.length <= 3) return 0
  return workflowTags.length - 3
}

const getExtraTagNames = (workflowTags: string[]) => {
  if (!workflowTags || workflowTags.length <= 3) return []
  return workflowTags.slice(3).map(tagId => getTagName(tagId))
}

onMounted(() => {
  loadTags()
  loadWorkflows()
})
</script>

<template>
  <a-spin :loading="loading" class="block h-full w-full">
    <div class="p-6 flex flex-col h-full">
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-2">
          <a-avatar :size="32" class="bg-blue-700">
            <icon-relation :size="18" />
          </a-avatar>
          <div class="text-lg font-medium text-gray-900">工作流广场</div>
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
            placeholder="搜索工作流"
            class="w-full sm:w-[240px] bg-white rounded-lg border-gray-300"
            @search="handleSearch"
          />
        </div>
      </div>

      <div class="flex-1 overflow-auto scrollbar-hide">
        <a-row :gutter="[20, 20]">
          <a-col v-for="workflow in workflows" :key="workflow.id" :span="6">
            <a-card hoverable class="h-full rounded-lg flex flex-col" :body-style="{ padding: '16px' }">
              <button type="button" class="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg flex-1" @click="handlePreview(workflow)">
                <!-- 顶部工作流名称和标签 -->
                <div class="flex items-center gap-3 mb-3">
                  <a-avatar :size="40" shape="square" :image-url="workflow.icon" />
                  <div class="flex-1 min-w-0">
                    <div class="text-base font-bold text-gray-900 truncate">{{ workflow.name }}</div>
                    <div class="flex items-center gap-1 flex-wrap">
                      <a-tag v-for="tag in getDisplayTags(workflow.tags)" :key="tag" size="small">
                        {{ getTagName(tag) }}
                      </a-tag>
                      <a-tag v-if="getExtraTagCount(workflow.tags) > 0" size="small" class="cursor-help" :title="getExtraTagNames(workflow.tags).join(', ')">
                        +{{ getExtraTagCount(workflow.tags) }}
                      </a-tag>
                    </div>
                  </div>
                </div>

                <!-- 工作流描述 -->
                <div class="text-sm text-gray-600 h-[60px] line-clamp-3">{{ workflow.description }}</div>
              </button>

              <!-- 操作按钮 -->
              <div class="flex items-center gap-2 mt-2 mb-2">
                <button type="button" class="flex items-center gap-1.5 px-3 h-8 rounded-full transition-all duration-200 hover:scale-105" :class="workflow.is_liked ? 'bg-red-50' : 'bg-gray-50'" @click.stop="handleLike(workflow)">
                  <svg width="16" height="16" viewBox="0 0 24 24" :fill="workflow.is_liked ? '#ef4444' : 'none'" :stroke="workflow.is_liked ? 'none' : '#ef4444'" stroke-width="2">
                    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                  </svg>
                  <span :class="workflow.is_liked ? 'text-red-600' : 'text-gray-600'" class="text-xs font-medium">{{ workflow.like_count }}</span>
                </button>

                <button type="button" class="flex items-center gap-1.5 px-3 h-8 rounded-full transition-all duration-200 hover:scale-105" :class="workflow.is_favorited ? 'bg-yellow-50' : 'bg-gray-50'" @click.stop="handleFavorite(workflow)">
                  <svg width="16" height="16" viewBox="0 0 24 24" :fill="workflow.is_favorited ? '#eab308' : 'none'" :stroke="workflow.is_favorited ? 'none' : '#eab308'" stroke-width="2">
                    <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>
                  </svg>
                  <span :class="workflow.is_favorited ? 'text-yellow-600' : 'text-gray-600'" class="text-xs font-medium">{{ workflow.favorite_count || 0 }}</span>
                </button>

                <button type="button" class="flex items-center gap-1.5 px-3 h-8 rounded-full transition-all duration-200 hover:scale-105" :class="workflow.is_forked ? 'bg-blue-50' : 'bg-gray-50'" @click.stop="handleFork(workflow)">
                  <icon-branch :size="16" :style="{ color: workflow.is_forked ? '#3b82f6' : '#9ca3af' }" />
                  <span :class="workflow.is_forked ? 'text-blue-600' : 'text-gray-600'" class="text-xs font-medium">{{ workflow.fork_count }}</span>
                </button>
              </div>

              <!-- 发布者和发布时间 -->
              <div class="flex items-center gap-1.5">
                <a-avatar :size="18" :image-url="workflow.account_avatar" />
                <div class="text-xs text-gray-400">{{ workflow.account_name || '匿名用户' }} · 发布于 {{ workflow.published_at > 0 ? formatTimestampShort(workflow.published_at) : '未知时间' }}</div>
              </div>
            </a-card>
          </a-col>
          <a-col v-if="workflows.length === 0" :span="24"><a-empty description="暂无工作流" class="py-20" /></a-col>
        </a-row>
      </div>

      <div v-if="total > pageSize" class="flex justify-center mt-6">
        <a-pagination :current="page" :page-size="pageSize" :total="total" show-total @change="handlePageChange" />
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
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
</style>
