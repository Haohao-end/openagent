<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  useDeleteSegment,
  useGetDocument,
  useGetSegmentsWithPage,
  useUpdateSegmentEnabled,
} from '@/hooks/use-dataset'
import CreateOrUpdateSegmentModal from './components/CreateOrUpdateSegmentModal.vue'
import { formatTimestampShort } from '@/utils/time-formatter'

// 1.定义页面所需的基础数据
const route = useRoute()
const router = useRouter()
const createOrUpdateModalVisible = ref(false)
const updateSegmentID = ref('')
const { document, loadDocument } = useGetDocument()
const { loading, segments, paginator, loadSegments } = useGetSegmentsWithPage()
const { handleDelete } = useDeleteSegment()
const { handleUpdate: handleUpdateSegmentEnabled } = useUpdateSegmentEnabled()

// 2.滚动数据分页处理器
const handleScroll = async (event: UIEvent) => {
  // 1.获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 2.判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (loading.value) {
      return
    }
    await loadSegments(
      String(route.params?.dataset_id),
      String(route.params?.document_id),
      false,
      String(route.query?.search_word ?? ''),
    )
  }
}

// 监听路由query的变化
watch(
  () => route.query?.search_word,
  (newValue) =>
    loadSegments(
      String(route.params?.dataset_id),
      String(route.params?.document_id),
      true,
      String(newValue),
    ),
)

// 3.页面DOM加载完毕时加载数据
onMounted(() => {
  loadDocument(String(route.params?.dataset_id), String(route.params?.document_id))
  loadSegments(
    String(route.params?.dataset_id),
    String(route.params?.document_id),
    true,
    String(route.query?.search_word ?? ''),
  )
})
</script>

<template>
  <!-- 调整边距+隐藏 -->
  <div class="px-6 pt-6 flex flex-col overflow-hidden h-full">
    <!-- 固定顶部 -->
    <div class="sticky top-0 z-20 bg-gray-50">
      <!-- 顶部回退按钮+文档详情 -->
      <div class="flex items-center w-full gap-2 mb-6">
        <!-- 左侧回退按钮 -->
        <router-link
          :to="{
            name: 'space-datasets-documents-list',
            params: {
              dataset_id: route.params?.dataset_id as string,
              document_id: route.params?.document_id as string,
            },
          }"
        >
          <a-button size="mini" type="text" class="!text-gray-700">
            <template #icon>
              <icon-left />
            </template>
          </a-button>
        </router-link>
        <!-- 右侧文档信息 -->
        <div class="flex items-center gap-3">
          <!-- 文档的图标 -->
          <a-avatar :size="40" shape="square" class="rounded-lg bg-blue-700">
            <icon-file />
          </a-avatar>
          <!-- 知识库信息 -->
          <div class="flex flex-col justify-between h-[40px]">
            <a-skeleton-line v-if="!document?.name" :widths="[100]" />
            <div v-else class="text-gray-700">文档 / {{ document.name }}</div>
            <div v-if="!document?.name" class="flex items-center gap-2">
              <a-skeleton-line :widths="[60]" :line-height="18" />
              <a-skeleton-line :widths="[60]" :line-height="18" />
              <a-skeleton-line :widths="[60]" :line-height="18" />
            </div>
            <div v-else class="flex items-center gap-2">
              <a-tag size="small" class="rounded h-[18px] leading-[18px] bg-gray-200 text-gray-500">
                {{ document.segment_count }} 文档片段
              </a-tag>
              <a-tag size="small" class="rounded h-[18px] leading-[18px] bg-gray-200 text-gray-500">
                {{ document.hit_count }} 命中
              </a-tag>
              <a-tag size="small" class="rounded h-[18px] leading-[18px] bg-gray-200 text-gray-500">
                {{ formatTimestampShort(document.updated_at) }} 最后编辑
              </a-tag>
            </div>
          </div>
        </div>
      </div>
      <!-- 中间检索以及功能按钮 -->
      <div class="flex items-center justify-between mb-6">
        <!-- 左侧搜索框 -->
        <a-input-search
          :default-value="route.query?.search_word || ''"
          placeholder="请输入关键词搜索片段"
          class="w-[240px] bg-white rounded-lg border-gray-200"
          @search="
            (value: string) => {
              router.push({
                path: route.path,
                query: { search_word: value },
              })
            }
          "
        />
        <!-- 右侧功能区 -->
        <a-space :size="12">
          <div
            class="flex items-center gap-2 h-8 leading-8 bg-white rounded-lg px-3 text-gray-700 border"
          >
            <div
              v-if="document.enabled"
              class="w-2 h-2 bg-green-500 border border-green-700 rounded-sm"
            ></div>
            <div v-else class="w-2 h-2 bg-gray-500 border border-gray-200 rounded-sm"></div>
            {{ document.enabled ? '可用' : '已禁用' }}
          </div>
          <a-button
            type="primary"
            class="rounded-lg"
            @click="
              () => {
                createOrUpdateModalVisible = true
                updateSegmentID = ''
              }
            "
          >
            <template #icon>
              <icon-file />
            </template>
            添加片段
          </a-button>
        </a-space>
      </div>
    </div>
    <!-- 中间列表区域 -->
    <a-spin
      :loading="loading"
      class="block h-full w-full scrollbar-w-none overflow-scroll"
      @scroll="handleScroll"
    >
      <!-- 片段列表 -->
      <a-row :gutter="[20, 20]">
        <!-- 有数据的UI状态 -->
        <a-col v-for="segment in segments" :key="segment.id" :span="6">
          <a-card hoverable class="cursor-pointer rounded-lg">
            <!-- 顶部片段位置及状态 -->
            <div class="flex items-center justify-between mb-2">
              <a-tag size="small" class="rounded-md text-gray-500">
                #{{ segment.position.toString().padStart(3, '0') }}
              </a-tag>
              <div class="flex items-center">
                <div class="flex items-center gap-1 text-xs text-gray-700">
                  {{ segment.enabled ? '已启用' : '已禁用' }}
                  <div
                    v-if="segment.enabled"
                    class="w-2 h-2 bg-green-500 border border-green-700 rounded-sm"
                  ></div>
                  <div v-else class="w-2 h-2 bg-gray-500 border border-gray-700 rounded-sm"></div>
                </div>
                <a-divider direction="vertical" />
                <a-switch
                  v-model:model-value="segment.enabled"
                  :disabled="segment.status !== 'completed'"
                  @change="
                    async (value) =>
                      await handleUpdateSegmentEnabled(
                        route.params?.dataset_id as string,
                        route.params?.document_id as string,
                        segment.id,
                        value as boolean,
                      )
                  "
                  type="round"
                  size="small"
                />
              </div>
            </div>
            <!-- 中间片段内容 -->
            <div
              class="leading-[18px] text-gray-700 h-[72px] line-clamp-4 mb-2 break-all"
              @click="
                () => {
                  updateSegmentID = segment.id
                  createOrUpdateModalVisible = true
                }
              "
            >
              {{ segment.content }}
            </div>
            <!-- 底部扩展信息 -->
            <div class="flex items-center justify-between">
              <!-- 左侧扩展 -->
              <div class="flex items-center gap-3">
                <div class="flex items-center gap-1 text-xs text-gray-500">
                  <icon-bookmark />
                  {{ segment.character_count }} 字符
                </div>
                <div class="flex items-center gap-1 text-xs text-gray-500">
                  <icon-pushpin />
                  {{ segment.hit_count }} 命中
                </div>
              </div>
              <!-- 右侧删除 -->
              <a-button
                type="text"
                size="mini"
                class="!text-gray-500"
                @click="
                  async () =>
                    await handleDelete(
                      route.params?.dataset_id as string,
                      route.params?.document_id as string,
                      segment.id,
                      () =>
                        loadSegments(
                          String(route.params?.dataset_id),
                          String(route.params?.document_id),
                          true,
                          String(route.query?.search_word ?? ''),
                        ),
                    )
                "
              >
                <template #icon>
                  <icon-delete />
                </template>
              </a-button>
            </div>
          </a-card>
        </a-col>
        <!-- 没数据的UI状态 -->
        <a-col v-if="segments.length === 0" :span="24">
          <a-empty
            description="没有可用的文档片段"
            class="h-[400px] flex flex-col items-center justify-center"
          />
        </a-col>
      </a-row>
      <!-- 加载器 -->
      <a-row v-if="paginator.total_page >= 2">
        <!-- 加载数据中 -->
        <a-col v-if="loading" :span="24" align="center">
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
    </a-spin>
    <!-- 新建/修改模态窗 -->
    <create-or-update-segment-modal
      v-model:visible="createOrUpdateModalVisible"
      :dataset_id="route.params?.dataset_id as string"
      :document_id="route.params?.document_id as string"
      :segment_id="updateSegmentID"
      :callback="
        () =>
          loadSegments(
            String(route.params?.dataset_id),
            String(route.params?.document_id),
            true,
            String(route.query?.search_word ?? ''),
          )
      "
    />
  </div>
</template>

<style scoped></style>
