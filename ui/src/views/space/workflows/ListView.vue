<script setup lang="ts">
import moment from 'moment/moment'
import { useDeleteWorkflow, useGetWorkflowsWithPage } from '@/hooks/use-workflow'
import { onMounted, ref, watch } from 'vue'
import { useAccountStore } from '@/stores/account'
import { useRoute, useRouter } from 'vue-router'
import CreateOrUpdateWorkflowModal from '@/views/space/workflows/components/CreateOrUpdateWorkflowModal.vue'
import CardGridSkeleton from '@/components/skeletons/CardGridSkeleton.vue'
import { getUserAvatarUrl } from '@/utils/helper'

// 1.定义页面所需数据
const route = useRoute()
const router = useRouter()
const props = defineProps({
  createType: { type: String, default: '', required: true },
})
const emits = defineEmits(['update:create-type'])
const createOrUpdateWorkflowModalVisible = ref(false)
const updateWorkflowId = ref('')
const accountStore = useAccountStore()
const {
  loading: getWorkflowsWithPageLoading,
  workflows,
  paginator,
  loadWorkflows,
} = useGetWorkflowsWithPage()
const { handleDeleteWorkflow } = useDeleteWorkflow()

// 2.定义滚动数据分页处理器
const handleScroll = (event: Event) => {
  // 1.获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const target = event.target as HTMLElement | null
  if (!target) return
  const { scrollTop, scrollHeight, clientHeight } = target

  // 2.判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (getWorkflowsWithPageLoading.value) return
    void loadWorkflows(String(route.query?.search_word ?? ''), '')
  }
}

// 页面DOM加载完毕后执行
onMounted(async () => {
  // 初始化工作流数据数据
  await loadWorkflows(String(route.query?.search_word ?? ''), '', true)
})

watch(
  () => props.createType,
  (newValue) => {
    if (newValue === 'workflow') {
      updateWorkflowId.value = ''
      createOrUpdateWorkflowModalVisible.value = true
      emits('update:create-type', '')
    }
  },
)

watch(
  () => route.query?.search_word,
  async () => await loadWorkflows(String(route.query?.search_word ?? ''), '', true),
)

// 3.定义卡片点击处理器
const handleCardClick = (workflowId: string) => {
  router.push({
    name: 'space-workflows-detail',
    params: { workflow_id: workflowId },
  })
}
</script>

<template>
  <div class="block h-full w-full scrollbar-w-none overflow-y-scroll overflow-x-hidden" @scroll="handleScroll">
    <card-grid-skeleton v-if="getWorkflowsWithPageLoading && workflows.length === 0" :count="8" />
    <template v-else>
      <!-- 底部工作流列表 -->
      <a-row :gutter="[20, 20]">
        <!-- 有数据的UI状态 -->
        <a-col
          v-for="workflow in workflows"
          :key="workflow.id"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
          :xl="6"
        >
          <a-card hoverable class="cursor-pointer rounded-lg" @click="handleCardClick(workflow.id)">
            <!-- 顶部工作流名称 -->
            <div class="flex items-center gap-3 mb-3">
              <!-- 左侧图标 -->
              <a-avatar :size="40" shape="square" :image-url="workflow.icon" />
              <!-- 右侧信息 -->
              <div class="flex flex-1 justify-between">
                <div class="flex flex-col">
                  <div class="text-base text-gray-900 font-bold">
                    {{ workflow.name }}
                    <icon-check-circle-fill
                      v-if="workflow.status === 'published'"
                      class="text-green-700"
                    />
                  </div>
                  <div class="text-xs text-gray-500 line-clamp-1">
                    {{ workflow.tool_call_name }} · {{ workflow.node_count }} 节点数
                  </div>
                </div>
                <!-- 操作按钮 -->
                <a-dropdown position="br" @click.stop>
                  <a-button type="text" size="small" class="rounded-lg !text-gray-700">
                    <template #icon>
                      <icon-more />
                    </template>
                  </a-button>
                  <template #content>
                    <a-doption
                      @click="
                        () => {
                          updateWorkflowId = workflow.id
                          createOrUpdateWorkflowModalVisible = true
                        }
                      "
                    >
                      编辑工作流
                    </a-doption>
                    <a-doption
                      class="text-red-700"
                      @click="
                        async () =>
                          await handleDeleteWorkflow(workflow.id, async () => {
                            await loadWorkflows(String(route.query?.search_word ?? ''), '', true)
                          })
                      "
                    >
                      删除
                    </a-doption>
                  </template>
                </a-dropdown>
              </div>
            </div>
            <!-- 工作流的描述信息 -->
            <div class="leading-[18px] text-gray-500 h-[72px] line-clamp-4 mb-2 break-all">
              {{ workflow.description }}
            </div>
            <!-- 应用的归属者信息 -->
            <div class="flex items-center gap-1.5">
              <a-avatar :size="18" class="bg-blue-700" :image-url="getUserAvatarUrl(accountStore.account.avatar, accountStore.account.name)">
                {{ (accountStore.account.name || '未知用户')[0] }}
              </a-avatar>
              <div class="text-xs text-gray-400">
                {{ accountStore.account.name }} · 最近编辑
                {{ moment(workflow.created_at * 1000).format('MM-DD HH:mm') }}
              </div>
            </div>
          </a-card>
        </a-col>
        <!-- 没数据的UI状态 -->
        <a-col v-if="workflows.length === 0" :span="24">
          <a-empty
            description="没有可用的工作流"
            class="h-[400px] flex flex-col items-center justify-center"
          />
        </a-col>
      </a-row>
      <!-- 加载器 -->
      <a-row v-if="paginator.total_page >= 2">
        <!-- 加载数据中 -->
        <a-col v-if="getWorkflowsWithPageLoading" :span="24" align="center">
          <a-space class="my-4">
            <a-spin />
            <div class="text-gray-400">加载中</div>
          </a-space>
        </a-col>
        <!-- 数据加载完成 -->
        <a-col v-else-if="paginator.current_page > paginator.total_page" :span="24" align="center">
          <div class="text-gray-400 my-4">数据已加载完成</div>
        </a-col>
      </a-row>
    </template>
    <!-- 新建/修改模态窗 -->
    <create-or-update-workflow-modal
      v-model:visible="createOrUpdateWorkflowModalVisible"
      v-model:workflow_id="updateWorkflowId"
      :callback="async () => await loadWorkflows(String(route.query?.search_word ?? ''), '', true)"
    />
  </div>
</template>

<style scoped>
:deep(.arco-row) {
  width: 100% !important;
  max-width: 100% !important;
}
</style>
