<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, inject } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import { cloneDeep, debounce } from 'lodash'
import { getReferencedVariables } from '@/utils/helper'
import { useGetDatasetsWithPage } from '@/hooks/use-dataset'
import { type ValidatedError, Message } from '@arco-design/web-vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/utils/error'
type DatasetItem = {
  id: string
  name: string
  icon: string
  description: string
}

type NodeInputField = {
  name: string
  type: string
  value: {
    type: string
    content: {
      ref_node_id: string
      ref_var_name: string
    }
  }
}

type FormInputField = {
  name: string
  type: string
  value: {
    type: string
    content: unknown
  }
  ref: string
  content?: unknown
}

type RetrievalConfig = {
  retrieval_strategy: string
  k: number
  score: number
}

type DatasetRetrievalNodeForm = {
  id: string
  type: string
  title: string
  description: string
  datasets: DatasetItem[]
  retrieval_config: RetrievalConfig
  inputs: FormInputField[]
  outputs: Array<Record<string, unknown>>
}

// 1.定义自定义组件所需数据
const props = defineProps({
  visible: { type: Boolean, required: true, default: false },
  node: {
    type: Object,
    required: true,
    default: () => {
      return {}
    },
  },
  loading: { type: Boolean, required: true, default: false },
})
const emits = defineEmits(['update:visible', 'updateNode'])
const datasetsModalVisible = ref(false)
const { t } = useI18n()
const form = ref<DatasetRetrievalNodeForm>({
  id: '',
  type: '',
  title: '',
  description: '',
  datasets: [],
  retrieval_config: {
    retrieval_strategy: 'semantic',
    k: 4,
    score: 0,
  },
  inputs: [],
  outputs: [],
})
const isSyncingForm = ref(false)

// 注入只读状态
const isReadonly = inject<boolean>('isReadonly', false)
const debounceAutoSave = debounce(() => {
  // 只读模式下不自动保存
  if (isReadonly) return
  void onSubmit({ errors: undefined })
}, 800)
const { nodes, edges } = useVueFlow()
const {
  loading: getDatasetsWithPageLoading,
  paginator,
  datasets,
  loadDatasets,
} = useGetDatasetsWithPage()
let isUnmounted = false
const handleLoadDatasets = async (init: boolean) => {
  try {
    await loadDatasets(init)
  } catch (error: unknown) {
    if (!isUnmounted) Message.error(getErrorMessage(error, t('workflowEditor.datasetRetrieval.loadFailed')))
  }
}

// 2.定义节点可引用的变量选项
const inputRefOptions = computed(() => {
  return getReferencedVariables(cloneDeep(nodes.value), cloneDeep(edges.value), props.node.id)
})

// 3.定义滚动数据分页处理器
const handleScroll = async (event: UIEvent) => {
  // 3.1 获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 3.2 判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (getDatasetsWithPageLoading.value) return
    await handleLoadDatasets(false)
  }
}

// 4.定义取消关联知识库函数
const removeDataset = (idx: number) => {
  form.value.datasets.splice(idx, 1)
}

// 5.知识库选择处理器
const handleSelectDataset = (idx: number) => {
  // 5.1 提取对应的知识库id
  const dataset = datasets.value[idx]

  // 5.2 检测id是否选中，如果是选中则删除
  if (form.value.datasets.some((activateDataset: DatasetItem) => activateDataset.id === dataset.id)) {
    form.value.datasets = form.value.datasets.filter(
      (activateDataset: DatasetItem) => activateDataset.id !== dataset.id,
    )
  } else {
    // 5.3 检测已关联的知识库数量
  if (form.value.datasets.length >= 5) {
      Message.warning(t('workflowEditor.datasetRetrieval.limitExceeded'))
      return
    }
    // 5.4 添加数据到激活知识库列表
    form.value.datasets.push({
      id: dataset.id,
      name: dataset.name,
      icon: dataset.icon,
      description: dataset.description,
    })
  }
}

// 6.定义表单提交函数
const onSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 6.1 检查表单是否出现错误，如果出现错误则直接结束
  if (errors) return

  // 6.2 深度拷贝表单数据内容
  const cloneInputs = cloneDeep(form.value.inputs)
  const cloneDatasets = cloneDeep(form.value.datasets)

  // 6.3 数据校验通过，通过事件触发数据更新
  emits('updateNode', {
    id: form.value.id,
    title: form.value.title,
    description: form.value.description,
    dataset_ids: cloneDatasets.map((dataset: DatasetItem) => {
      return dataset.id
    }),
    meta: { datasets: cloneDatasets },
    retrieval_config: cloneDeep(form.value.retrieval_config),
    inputs: cloneInputs.map((input: FormInputField) => {
      return {
        name: input.name,
        description: '',
        required: true,
        type: input.type === 'ref' ? 'string' : input.type,
        value: {
          type: input.type === 'ref' ? 'ref' : 'literal',
          content:
            input.type === 'ref'
              ? {
                  ref_node_id: input.ref.split('/')[0] || '',
                  ref_var_name: input.ref.split('/')[1] || '',
                }
              : input.content,
        },
        meta: {},
      }
    }),
    outputs: cloneDeep(form.value.outputs),
  })
}

// 7.监听数据，将数据映射到表单模型上
watch(
  () => props.node?.id,
  () => {
    const newNode = props.node
    if (!newNode?.id) return
    isSyncingForm.value = true
    debounceAutoSave.flush()
    debounceAutoSave.cancel()
    const cloneInputs = cloneDeep(newNode.data.inputs)
    form.value = {
      id: newNode.id,
      type: newNode.type,
      title: newNode.data.title,
      description: newNode.data.description,
      datasets: cloneDeep(newNode.data.meta?.datasets) ?? [],
      retrieval_config: cloneDeep(newNode.data.retrieval_config) ?? {
        k: 4,
        retrieval_strategy: 'semantic',
        score: 0,
      },
      inputs: cloneInputs.map((input: NodeInputField) => {
        // 7.1 计算引用的变量值信息
        const ref =
          input.value.type === 'ref'
            ? `${input.value.content.ref_node_id}/${input.value.content.ref_var_name}`
            : ''

        // 7.2 判断引用的变量值信息是否存在，如果不存在则设置为空
        let refExists = false
        if (input.value.type === 'ref') {
          for (const inputRefOption of inputRefOptions.value) {
            for (const option of inputRefOption.options) {
              if (option.value === ref) {
                refExists = true
                break
              }
            }
          }
        }
        return {
          name: input.name, // 变量名
          type: input.value.type === 'literal' ? input.type : 'ref', // 数据类型(涵盖ref/string/int/float/boolean
          content: input.value.type === 'literal' ? input.value.content : '', // 变量值内容
          ref: input.value.type === 'ref' && refExists ? ref : '', // 变量引用信息，存储引用节点id+引用变量名
        }
      }),
      outputs: [
        { name: 'combine_documents', type: 'string', value: { type: 'generated', content: '' } },
      ],
    }
    nextTick(() => {
      isSyncingForm.value = false
    })
  },
  { immediate: true },
)

watch(
  form,
  () => {
    if (isSyncingForm.value) return
    debounceAutoSave()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  isUnmounted = true
  debounceAutoSave.flush()
  debounceAutoSave.cancel()
})

onMounted(() => {
  void handleLoadDatasets(true)
})
</script>

<template>
  <div
    id="dataset-retrieval-node-info"
    class="absolute top-0 right-0 bottom-0 w-[400px] border-l z-50 bg-white overflow-scroll scrollbar-w-none p-3"
  >    <!-- 只读模式提示横幅 -->
    <div v-if="isReadonly" class="mb-3 p-3 bg-orange-50 border border-orange-200 rounded-lg">
      <div class="flex items-center gap-2 text-orange-700">
        <icon-lock class="flex-shrink-0" />
        <span class="text-sm font-medium">{{ t('workflowEditor.previewMode') }}</span>
      </div>
    </div>


    <!-- 顶部标题信息 -->
    <div class="flex items-center justify-between gap-3 mb-2">
      <!-- 左侧标题 -->
      <div class="flex items-center gap-1 flex-1">
        <a-avatar :size="30" shape="square" class="bg-violet-500 rounded-lg flex-shrink-0">
          <icon-storage />
        </a-avatar>
        <a-input
          v-model:model-value="form.title"
          :disabled="isReadonly"
          :placeholder="t('workflowEditor.titlePlaceholder')"
          class="!bg-white text-gray-700 font-semibold px-2"
        />
      </div>
      <!-- 右侧关闭按钮 -->
      <a-button
        type="text"
        size="mini"
        class="!text-gray700 flex-shrink-0"
        @click="() => emits('update:visible', false)"
      >
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>
    <!-- 描述信息 -->
    <a-textarea
      :auto-size="{ minRows: 3, maxRows: 5 }"
      v-model="form.description"
      :disabled="isReadonly"
      class="rounded-lg text-gray-700 !text-xs"
      :placeholder="t('workflowEditor.descriptionPlaceholder')"
    />
    <!-- 分隔符 -->
    <a-divider class="my-2" />
    <!-- 表单信息 -->
    <a-form size="mini" :model="form" :disabled="isReadonly" layout="vertical">
      <!-- 输入参数 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">{{ t('workflowEditor.inputParameters') }}</div>
            <a-tooltip :content="t('workflowEditor.modelConfig.help')">
              <icon-question-circle />
            </a-tooltip>
          </div>
        </div>
        <!-- 字段名 -->
        <div class="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <div class="w-[20%]">{{ t('workflowEditor.parameterName') }}</div>
          <div class="w-[25%]">{{ t('workflowEditor.parameterType') }}</div>
          <div class="w-[55%]">{{ t('workflowEditor.parameterValue') }}</div>
        </div>
        <!-- 循环遍历字段列表 -->
        <div v-for="(input, idx) in form?.inputs" :key="idx" class="flex items-center gap-1">
          <div class="w-[20%] flex-shrink-0">
            <div class="text-xs text-gray-500">{{ input.name }}</div>
          </div>
          <div class="w-[25%] flex-shrink-0">
            <a-select
              size="mini"
              v-model="input.type"
              class="px-2"
              :options="[
                { label: t('workflowEditor.variableTypes.ref'), value: 'ref' },
                { label: t('workflowEditor.variableTypes.string'), value: 'string' },
                { label: t('workflowEditor.variableTypes.int'), value: 'int' },
                { label: t('workflowEditor.variableTypes.float'), value: 'float' },
                { label: t('workflowEditor.variableTypes.boolean'), value: 'boolean' },
              ]"
            />
          </div>
          <div class="w-[55%] flex-shrink-0 flex items-center gap-1">
            <a-input
              v-if="input.type !== 'ref'"
              size="mini"
              v-model="input.content"
              :placeholder="t('workflowEditor.parameterValue')"
            />
            <a-select
              v-else
              :placeholder="t('workflowEditor.selectReference')"
              size="mini"
              tag-nowrap
              v-model="input.ref"
              :options="inputRefOptions"
            />
          </div>
        </div>
      </div>
      <a-divider class="my-4" />
      <!-- 检索策略 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">{{ t('workflowEditor.datasetRetrieval.title') }}</div>
            <a-tooltip :content="t('workflowEditor.datasetRetrieval.help')">
              <icon-question-circle />
            </a-tooltip>
          </div>
        </div>
        <a-radio-group
          v-model="form.retrieval_config.retrieval_strategy"
          default-value="semantic"
          :options="[
            { label: t('workflowEditor.datasetRetrieval.strategyHybrid'), value: 'hybrid' },
            { label: t('workflowEditor.datasetRetrieval.strategyFullText'), value: 'full_text' },
            { label: t('workflowEditor.datasetRetrieval.strategySemantic'), value: 'semantic' },
          ]"
        />
      </div>
      <a-divider class="my-4" />
      <!-- 最大召回数量 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">{{ t('workflowEditor.datasetRetrieval.maxRecallTitle') }}</div>
            <a-tooltip :content="t('workflowEditor.datasetRetrieval.maxRecallHelp')">
              <icon-question-circle />
            </a-tooltip>
          </div>
        </div>
        <div class="flex items-center gap-4 w-full pl-3">
          <a-slider v-model="form.retrieval_config.k" :step="1" :min="1" :max="10" />
          <a-input-number
            size="mini"
            v-model="form.retrieval_config.k"
            class="w-[80px]"
            :default-value="4"
          />
        </div>
      </div>
      <a-divider class="my-4" />
      <!-- 最小匹配度 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">{{ t('workflowEditor.datasetRetrieval.minScoreTitle') }}</div>
            <a-tooltip :content="t('workflowEditor.datasetRetrieval.minScoreHelp')">
              <icon-question-circle />
            </a-tooltip>
          </div>
        </div>
        <div class="flex items-center gap-4 w-full pl-3">
          <a-slider v-model="form.retrieval_config.score" :step="0.01" :min="0" :max="0.99" />
          <a-input-number
            size="mini"
            v-model="form.retrieval_config.score"
            class="w-[80px]"
            :min="0"
            :max="0.99"
            :step="0.01"
            :precision="2"
            :default-value="0.5"
          />
        </div>
      </div>
      <a-divider class="my-4" />
      <!-- 关联知识库 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">{{ t('workflowEditor.datasetRetrieval.bindDataset') }}</div>
            <a-tooltip :content="t('workflowEditor.datasetRetrieval.bindDatasetHelp')">
              <icon-question-circle />
            </a-tooltip>
          </div>
          <!-- 右侧关联知识库按钮 -->
          <a-button
            size="mini"
            type="text"
            class="!text-gray-700"
            @click="() => (datasetsModalVisible = true)"
          >
            <template #icon>
              <icon-plus />
            </template>
          </a-button>
        </div>
        <div v-if="form.datasets?.length > 0" class="flex flex-col gap-1">
          <div
            v-for="(dataset, idx) in form.datasets"
            :key="dataset.id"
            class="flex items-center justify-between bg-white p-3 rounded-lg cursor-pointer hover:shadow-sm group border"
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
              v-if="!isReadonly"
              size="mini"
              type="text"
              class="hidden group-hover:block flex-shrink-0 ml-2 !text-red-700 rounded"
              @click="() => removeDataset(idx)"
            >
              <template #icon>
                <icon-delete />
              </template>
            </a-button>
          </div>
        </div>
        <div v-else class="text-xs text-gray-500 leading-[22px]">
          {{ t('workflowEditor.datasetRetrieval.emptyTip') }}
        </div>
      </div>
      <a-divider class="my-4" />
      <!-- 输出参数 -->
      <div class="flex flex-col gap-2">
        <!-- 输出标题 -->
        <div class="font-semibold text-gray-700">{{ t('workflowEditor.outputData') }}</div>
        <!-- 字段标题 -->
        <div class="text-gray-500 text-xs">{{ t('workflowEditor.parameterName') }}</div>
        <!-- 输出参数列表 -->
        <div v-for="(output, idx) in form?.outputs" :key="idx" class="flex flex-col gap-2">
          <div class="flex items-center gap-2">
            <div class="text-gray-700">{{ output.name }}</div>
            <div class="text-gray-500 bg-gray-200 px-1 py-0.5 rounded">{{ output.type }}</div>
          </div>
        </div>
      </div>
    </a-form>
    <!-- 关联知识库 -->
    <a-modal
      :visible="datasetsModalVisible"
      hide-title
      :footer="false"
      :width="400"
      modal-class="h-[calc(100vh-32px)]"
      @cancel="() => (datasetsModalVisible = false)"
    >
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between mb-6">
        <div class="text-lg font-bold text-gray-700">{{ t('workflowEditor.datasetRetrieval.chooseDatasetTitle') }}</div>
        <a-button
          type="text"
          class="!text-gray-700"
          size="small"
          @click="() => (datasetsModalVisible = false)"
        >
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 中间知识库容器 -->
      <div class="h-[calc(100vh-180px)] mb-4 overflow-scroll scrollbar-w-none">
        <a-spin
          :loading="getDatasetsWithPageLoading"
          class="block h-full w-full scrollbar-w-none overflow-scroll"
          @scroll="handleScroll"
        >
          <!-- 知识库列表 -->
          <div class="flex flex-col gap-2">
            <!-- 有数据UI状态 -->
            <div
              v-for="(dataset, idx) in datasets"
              :key="dataset.id"
              :class="`flex items-center gap-2 border px-3 py-2 rounded-lg cursor-pointer hover:bg-blue-50 hover:border-blue-700 ${form.datasets.some((activateDataset: DatasetItem) => activateDataset.id === dataset.id) ? 'bg-blue-50 border-blue-700' : ''}`"
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
              v-if="datasets.length === 0"
              :description="t('workflowEditor.datasetRetrieval.noAvailable')"
              class="h-[400px] flex flex-col items-center justify-center"
            />
          </div>
          <!-- 加载器 -->
          <a-row v-if="paginator.total_page >= 2">
            <!-- 加载数据中 -->
            <a-col
              v-if="getDatasetsWithPageLoading"
              :span="24"
              class="!text-center"
            >
              <a-space class="my-4">
                <a-spin />
                <div class="text-gray-400">{{ t('workflowEditor.datasetRetrieval.loading') }}</div>
              </a-space>
            </a-col>
            <!-- 数据加载完成 -->
            <a-col v-else-if="paginator.current_page > paginator.total_page" :span="24" class="!text-center">
              <div class="text-gray-400 my-4">{{ t('workflowEditor.datasetRetrieval.loaded') }}</div>
            </a-col>
          </a-row>
        </a-spin>
      </div>
      <!-- 底部选中知识库及按钮 -->
      <div class="flex items-center justify-between">
        <!-- 左侧提示文字 -->
        <div class="">{{ t('workflowEditor.datasetRetrieval.selectedCount', { count: form.datasets.length }) }}</div>
        <!-- 按钮组 -->
        <a-space :size="12">
          <a-button type="primary" class="rounded-lg" @click="() => (datasetsModalVisible = false)">
            {{ t('workflowEditor.datasetRetrieval.chooseDatasetButton') }}
          </a-button>
        </a-space>
      </div>
    </a-modal>
  </div>
</template>
