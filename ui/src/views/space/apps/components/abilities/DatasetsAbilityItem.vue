<script setup lang="ts">
import { nextTick, onMounted, type PropType, ref, watch } from 'vue'
import { useUpdateDraftAppConfig } from '@/hooks/use-app'
import { useGetDatasetsWithPage } from '@/hooks/use-dataset'
import { cloneDeep, isEqual } from 'lodash'
import { Message } from '@arco-design/web-vue'

type DatasetSelection = {
  id: string
  name: string
  icon: string
  description: string
}

type RetrievalConfigForm = {
  retrieval_strategy: string
  k: number
  score: number
}

// 1.定义自定义组件所需数据
const props = defineProps({
  app_id: { type: String, default: '', required: true },
  retrieval_config: {
    type: Object as PropType<RetrievalConfigForm>,
    default: () => ({
      retrieval_strategy: 'semantic',
      k: 4,
      score: 0,
    }),
    required: true,
  },
  datasets: {
    type: Array as PropType<DatasetSelection[]>,
    default: () => [],
    required: true,
  },
})
const emits = defineEmits(['update:datasets', 'update:retrieval_config'])
const { loading: updateDraftAppConfigLoading, handleUpdateDraftAppConfig } =
  useUpdateDraftAppConfig()
const { loading, paginator, datasets: apiDatasets, loadDatasets } = useGetDatasetsWithPage()
const datasetsModalVisible = ref(false)
const retrievalConfigModalVisible = ref(false)
const isDatasetsInit = ref(false)
const activateDatasets = ref<DatasetSelection[]>([])
const originDatasets = ref<DatasetSelection[]>([])
const retrievalConfigForm = ref<RetrievalConfigForm>({
  retrieval_strategy: 'semantic',
  k: 4,
  score: 0,
})
const originRetrievalConfigForm = ref<RetrievalConfigForm>({
  retrieval_strategy: 'semantic',
  k: 4,
  score: 0,
})
const isRetrievalConfigInit = ref(false)

// 2.定义滚动数据分页处理器
const handleScroll = async (event: UIEvent) => {
  // 2.1 获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 2.2 判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (loading.value) return
    await loadDatasets()
  }
}

// 3.定义判断知识库数据是否发生变化函数
const isDatasetsModified = () => {
  return isEqual(activateDatasets.value, originDatasets.value)
}

// 4.定义判断检索设置是否发生变化函数
const isRetrievalConfigFormModified = () => {
  return isEqual(retrievalConfigForm.value, originRetrievalConfigForm.value)
}

// 5.定义取消模态窗处理器
const handleCancelDatasetsModal = () => {
  // 5.1 隐藏模态窗
  datasetsModalVisible.value = false

  // 5.2 还原初始值
  activateDatasets.value = originDatasets.value
  isDatasetsInit.value = false
}

// 6.定义取消检索设置模态窗处理器
const handleCancelRetrievalConfigModal = () => {
  // 6.1 隐藏模态窗
  retrievalConfigModalVisible.value = false

  // 6.2 还原初始值
  retrievalConfigForm.value = originRetrievalConfigForm.value
  isRetrievalConfigInit.value = false
}

// 7.知识库选择处理器
const handleSelectDataset = (idx: number) => {
  // 7.1 提取对应的知识库id
  const dataset = apiDatasets.value[idx]

  // 7.2 检测id是否选中，如果是选中则删除
  if (activateDatasets.value.some((activateDataset) => activateDataset.id === dataset.id)) {
    activateDatasets.value = activateDatasets.value.filter(
      (activateDataset) => activateDataset.id !== dataset.id,
    )
  } else {
    // 7.3 检测已关联的知识库数量
    if (activateDatasets.value.length >= 5) {
      Message.warning('关联知识库已超过5个，无法继续关联')
      return
    }
    // 7.4 添加数据到激活知识库列表
    activateDatasets.value.push({
      id: dataset.id,
      name: dataset.name,
      icon: dataset.icon,
      description: dataset.description,
    })
  }
}

// 8.提交更新关联知识库
const handleSubmitDatasets = async () => {
  // 8.1 处理数据并完成API接口提交
  await handleUpdateDraftAppConfig(props.app_id, {
    datasets: activateDatasets.value.map((activateDataset) => activateDataset.id),
  })

  // 8.2 接口更新更新成功，同步表单信息
  originDatasets.value = activateDatasets.value
  await nextTick()

  // 8.3 双向同步更新props中的数据
  emits('update:datasets', activateDatasets.value)

  // 8.4 隐藏模态窗
  handleCancelDatasetsModal()
}

// 9.提交更新检索配置
const handleSubmitRetrievalConfig = async () => {
  const retrievalConfig = {
    retrieval_strategy: String(retrievalConfigForm.value.retrieval_strategy || 'semantic'),
    k: Number(retrievalConfigForm.value.k ?? 4),
    score: Number(retrievalConfigForm.value.score ?? 0),
  }

  // 9.1 处理数据并完成API接口提交
  await handleUpdateDraftAppConfig(props.app_id, {
    retrieval_config: retrievalConfig,
  })

  // 9.2 接口更新更新成功，同步表单信息
  originRetrievalConfigForm.value = retrievalConfig

  // 9.3 双向同步更新props中的数据
  emits('update:retrieval_config', retrievalConfig)

  // 9.4 隐藏模态窗
  handleCancelRetrievalConfigModal()
}

// 10.监听草稿配置关联的知识库列表
watch(
  () => props.datasets,
  (newValue) => {
    // 10.1 检测数据是否初始化
    if (!isDatasetsInit.value || !isDatasetsModified()) {
      // 10.2 判断草稿配置是否已传递配置
      if (newValue && newValue.length > 0) {
        // 10.3 赋初始值
        const initData = props.datasets.map((dataset) => {
          return {
            id: dataset.id,
            name: dataset.name,
            icon: dataset.icon,
            description: dataset.description,
          }
        })
        activateDatasets.value = cloneDeep(initData)
        originDatasets.value = cloneDeep(initData)

        // 10.4 修改初始化状态
        isDatasetsInit.value = true
      }
    }
  },
  { immediate: true, deep: true },
)

// 11.监听检索配置
watch(
  () => props.retrieval_config,
  (newValue) => {
    // 11.1 检测是否是否更新并且未初始化
    if (!isRetrievalConfigInit.value || !isRetrievalConfigFormModified()) {
      if (newValue && Object.keys(newValue).length > 0) {
        // 11.2 更新表单数据和备份数据
        retrievalConfigForm.value = { ...newValue }
        originRetrievalConfigForm.value = { ...newValue }

        // 11.3 标记为已初始化
        isRetrievalConfigInit.value = true
      }
    }
  },
  { immediate: true, deep: true },
)

// 12.监听知识库模态窗显示or隐藏
watch(
  () => datasetsModalVisible.value,
  async (newValue) => {
    // 12.1 显示状态，重新加载数据，获取最新的知识库列表
    if (newValue) {
      await loadDatasets(true)
    } else {
      // 12.2 隐藏状态，清空数据
      apiDatasets.value.splice(0, apiDatasets.value.length)
    }
  },
)

onMounted(() => {
  loadDatasets(true)
})
</script>

<template>
  <div class="">
    <a-collapse-item key="datasets" class="app-ability-item">
      <template #header>
        <div class="text-gray-700 font-bold">知识库</div>
      </template>
      <template #extra>
        <a-space>
          <a-button
            size="mini"
            class="rounded-lg px-2"
            @click.stop="retrievalConfigModalVisible = true"
          >
            <template #icon>
              <icon-language />
            </template>
            <div v-if="retrieval_config?.retrieval_strategy === 'semantic'" class="">
              相似性检索
            </div>
            <div v-else-if="retrieval_config?.retrieval_strategy === 'full_text'" class="">
              全文检索
            </div>
            <div v-else class="">混合检索</div>
          </a-button>
          <a-button
            size="mini"
            type="text"
            class="!text-gray-700"
            @click.stop="datasetsModalVisible = true"
          >
            <template #icon>
              <icon-plus />
            </template>
          </a-button>
        </a-space>
      </template>
      <div v-if="props.datasets?.length > 0" class="flex flex-col gap-1">
        <div
          v-for="(dataset, idx) in props.datasets"
          :key="dataset.id"
          class="flex items-center justify-between bg-white p-3 rounded-lg cursor-pointer hover:shadow-sm group"
        >
          <!-- 左侧知识库信息 -->
          <div class="flex items-center gap-2">
            <!-- 图标 -->
            <a-avatar
              :size="36"
              shape="square"
              class="rounded flex-shrink-0"
              :image-url="dataset.icon"
            />
            <!-- 名称与描述信息 -->
            <div class="flex flex-col flex-1 gap-1 h-9">
              <div class="text-gray-700 font-bold leading-[18px] line-clamp-1 break-all">
                {{ dataset.name }}
              </div>
              <div class="text-gray-500 text-xs line-clamp-1 break-all">
                {{ dataset.description }}
              </div>
            </div>
          </div>
          <!-- 右侧删除按钮 -->
          <a-button
            size="mini"
            type="text"
            class="hidden group-hover:block flex-shrink-0 ml-2 !text-red-700 rounded"
            @click="
              async () => {
                // 1.清除props中指定的数据
                const newDatasets = [...props.datasets]
                newDatasets.splice(idx, 1)

                // 2.提交草稿配置到接口
                await handleUpdateDraftAppConfig(props.app_id, {
                  datasets: newDatasets.map((item) => item.id),
                })

                // 3.更新数据并确保数据完成更新
                isDatasetsInit = false
                emits('update:datasets', newDatasets)
              }
            "
          >
            <template #icon>
              <icon-delete />
            </template>
          </a-button>
        </div>
      </div>
      <div v-else class="text-xs text-gray-500 leading-[22px]">
        引用文本类型的数据，实现知识问答，应用最多支持关联 5 个知识库。
      </div>
    </a-collapse-item>
    <!-- 知识库模态窗 -->
    <a-modal
      :visible="datasetsModalVisible"
      hide-title
      :footer="false"
      :width="400"
      class="datasets-modal"
      modal-class="h-[calc(100vh-32px)] right-4"
      @cancel="handleCancelDatasetsModal"
    >
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between mb-6">
        <div class="text-lg font-bold text-gray-700">选择引用知识库</div>
        <a-button
          type="text"
          class="!text-gray-700"
          size="small"
          @click="handleCancelDatasetsModal"
        >
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 中间知识库容器 -->
      <div class="h-[calc(100vh-180px)] mb-4 overflow-scroll scrollbar-w-none">
        <a-spin
          :loading="loading"
          class="block h-full w-full scrollbar-w-none overflow-scroll"
          @scroll="handleScroll"
        >
          <!-- 知识库列表 -->
          <div class="flex flex-col gap-2">
            <!-- 有数据UI状态 -->
            <div
              v-for="(dataset, idx) in apiDatasets"
              :key="dataset.id"
              :class="`flex items-center gap-2 border px-3 py-2 rounded-lg cursor-pointer hover:bg-blue-50 hover:border-blue-700 ${activateDatasets.some((activateDataset) => activateDataset.id === dataset.id) ? 'bg-blue-50 border-blue-700' : ''}`"
              @click="() => handleSelectDataset(idx)"
            >
              <a-avatar
                :size="24"
                shape="square"
                class="flex-shrink-0 rounded"
                :image-url="dataset.icon"
              />
              <div class="line-clamp-1 text-gray-500 flex-1">{{ dataset.name }}</div>
            </div>
            <!-- 无数据UI状态 -->
            <a-empty
              v-if="apiDatasets.length === 0"
              description="没有可用的知识库"
              class="h-[400px] flex flex-col items-center justify-center"
            />
          </div>
          <!-- 加载器 -->
          <a-row v-if="paginator.total_page >= 2">
            <!-- 加载数据中 -->
            <a-col
              v-if="loading"
              :span="24"
              class="!text-center"
            >
              <a-space class="my-4">
                <a-spin />
                <div class="text-gray-400">加载中</div>
              </a-space>
            </a-col>
            <!-- 数据加载完成 -->
            <a-col v-else-if="paginator.current_page > paginator.total_page" :span="24" class="!text-center">
              <div class="text-gray-400 my-4">数据已加载完成</div>
            </a-col>
          </a-row>
        </a-spin>
      </div>
      <!-- 底部选中知识库及按钮 -->
      <div class="flex items-center justify-between">
        <!-- 左侧提示文字 -->
        <div class="">{{ activateDatasets.length }} 个知识库被选中</div>
        <!-- 按钮组 -->
        <a-space :size="12">
          <a-button class="rounded-lg" @click="handleCancelDatasetsModal">取消</a-button>
          <a-button
            :loading="updateDraftAppConfigLoading"
            type="primary"
            class="rounded-lg"
            @click="handleSubmitDatasets"
          >
            添加
          </a-button>
        </a-space>
      </div>
    </a-modal>
    <!-- 检索设置模态窗 -->
    <a-modal
      :visible="retrievalConfigModalVisible"
      hide-title
      :footer="false"
      modal-class="rounded-xl"
      @cancel="handleCancelRetrievalConfigModal"
    >
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between">
        <div class="text-lg font-bold text-gray-700">检索设置</div>
        <a-button
          type="text"
          class="!text-gray-700"
          size="small"
          @click="handleCancelRetrievalConfigModal"
        >
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 中间表单内容 -->
      <a-form :model="retrievalConfigForm" @submit="handleSubmitRetrievalConfig" class="pt-6">
        <a-form-item field="retrieval_strategy" label="检索策略" label-align="left">
          <a-radio-group
            v-model:model-value="retrievalConfigForm.retrieval_strategy"
            default-value="semantic"
            :options="[
              { label: '混合策略', value: 'hybrid' },
              { label: '全文检索', value: 'full_text' },
              { label: '相似性检索', value: 'semantic' },
            ]"
          />
        </a-form-item>
        <a-form-item field="k" label="最大召回数量">
          <div class="flex items-center gap-4 w-full pl-3">
            <a-slider v-model:model-value="retrievalConfigForm.k" :step="1" :min="1" :max="10" />
            <a-input-number
              v-model:model-value="retrievalConfigForm.k"
              class="w-[80px]"
              :default-value="4"
            />
          </div>
        </a-form-item>
        <a-form-item field="score" label="最小匹配度">
          <div class="flex items-center gap-4 w-full pl-3">
            <a-slider
              v-model:model-value="retrievalConfigForm.score"
              :step="0.01"
              :min="0"
              :max="0.99"
            />
            <a-input-number
              v-model:model-value="retrievalConfigForm.score"
              class="w-[80px]"
              :min="0"
              :max="0.99"
              :step="0.01"
              :precision="2"
              :default-value="0.5"
            />
          </div>
        </a-form-item>
        <!-- 底部按钮 -->
        <div class="flex items-center justify-between">
          <div class=""></div>
          <a-space :size="16">
            <a-button class="rounded-lg" @click="handleCancelRetrievalConfigModal">取消</a-button>
            <a-button
              :loading="updateDraftAppConfigLoading"
              type="primary"
              html-type="submit"
              class="rounded-lg"
            >
              保存
            </a-button>
          </a-space>
        </div>
      </a-form>
    </a-modal>
  </div>
</template>

<style>
.datasets-modal {
  .arco-modal-wrapper {
    @apply text-right;
  }
}
</style>
