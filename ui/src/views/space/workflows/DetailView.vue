<script setup lang="ts">
import { markRaw, onBeforeUnmount, onMounted, ref, computed, defineAsyncComponent, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ConnectionMode, Panel, useVueFlow, VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { MiniMap } from '@vue-flow/minimap'
import { debounce } from 'lodash'
import { useI18n } from 'vue-i18n'
import {
  useCancelPublishWorkflow,
  useGetDraftGraph,
  useGetWorkflow,
  usePublishWorkflow,
  useUpdateDraftGraph,
  useShareWorkflow,
} from '@/hooks/use-workflow'
import StartNode from './components/nodes/StartNode.vue'
import LlmNode from './components/nodes/LLMNode.vue'
import DatasetRetrievalNode from './components/nodes/DatasetRetrievalNode.vue'
import CodeNode from './components/nodes/CodeNode.vue'
import HttpRequestNode from './components/nodes/HttpRequestNode.vue'
import ToolNode from './components/nodes/ToolNode.vue'
import TemplateTransformNode from './components/nodes/TemplateTransformNode.vue'
import EndNode from './components/nodes/EndNode.vue'
import TextProcessorNode from './components/nodes/TextProcessorNode.vue'
import VariableAssignerNode from './components/nodes/VariableAssignerNode.vue'
import ParameterExtractorNode from './components/nodes/ParameterExtractorNode.vue'
import IfElseNode from './components/nodes/IfElseNode.vue'
import DebugModal from './components/DebugModal.vue'
import StartNodeInfo from './components/infos/StartNodeInfo.vue'
import LlmNodeInfo from './components/infos/LLMNodeInfo.vue'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/minimap/dist/style.css'
import { Message } from '@arco-design/web-vue'
import TemplateTransformNodeInfo from '@/views/space/workflows/components/infos/TemplateTransformNodeInfo.vue'
import HttpRequestNodeInfo from '@/views/space/workflows/components/infos/HttpRequestNodeInfo.vue'
import DatasetRetrievalNodeInfo from '@/views/space/workflows/components/infos/DatasetRetrievalNodeInfo.vue'
import ToolNodeInfo from '@/views/space/workflows/components/infos/ToolNodeInfo.vue'
import EndNodeInfo from '@/views/space/workflows/components/infos/EndNodeInfo.vue'
import TextProcessorNodeInfo from '@/views/space/workflows/components/infos/TextProcessorNodeInfo.vue'
import VariableAssignerNodeInfo from '@/views/space/workflows/components/infos/VariableAssignerNodeInfo.vue'
import ParameterExtractorNodeInfo from '@/views/space/workflows/components/infos/ParameterExtractorNodeInfo.vue'
import IfElseNodeInfo from '@/views/space/workflows/components/infos/IfElseNodeInfo.vue'
import { useWorkflowCanvasInteraction } from '@/views/space/workflows/use-workflow-canvas-interaction'
import { loadWorkflowDetailByMode } from '@/views/space/workflows/use-workflow-detail-loader'
import { useWorkflowHeader } from '@/views/space/workflows/use-workflow-header'
import { useWorkflowNodeSidebar } from '@/views/space/workflows/use-workflow-node-sidebar'
import { useWorkflowPublishActions } from '@/views/space/workflows/use-workflow-publish-actions'

const CodeNodeInfo = defineAsyncComponent(
  () => import('@/views/space/workflows/components/infos/CodeNodeInfo.vue'),
)

// 1.定义页面所需数据
const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const workflowId = ref<string>(String(route.params?.workflow_id ?? '')) // 缓存 workflow_id，避免路由切换时丢失
const isPreviewMode = computed(() => route.name === 'store-workflows-preview') // 判断是否为预览模式
const NOTE_TYPES = {
  start: markRaw(StartNode),
  llm: markRaw(LlmNode),
  tool: markRaw(ToolNode),
  dataset_retrieval: markRaw(DatasetRetrievalNode),
  template_transform: markRaw(TemplateTransformNode),
  http_request: markRaw(HttpRequestNode),
  code: markRaw(CodeNode),
  text_processor: markRaw(TextProcessorNode),
  variable_assigner: markRaw(VariableAssignerNode),
  parameter_extractor: markRaw(ParameterExtractorNode),
  if_else: markRaw(IfElseNode),
  end: markRaw(EndNode),
}
const NODE_DATA_MAP = computed<Record<string, Record<string, unknown>>>(() => ({
  start: {
    title: t('workflowEditor.nodePalette.start.title'),
    description: t('workflowEditor.nodePalette.start.description'),
    inputs: [],
  },
  llm: {
    title: t('workflowEditor.nodePalette.llm.title'),
    description: t('workflowEditor.nodePalette.llm.description'),
    prompt: '',
    model_config: {
      provider: 'openai',
      model: 'gpt-4o-mini',
      parameters: {
        frequency_penalty: 0.2,
        max_tokens: 8192,
        presence_penalty: 0.2,
        temperature: 0.5,
        top_p: 0.85,
      },
    },
    inputs: [],
    outputs: [{ name: 'output', type: 'string', value: { type: 'generated', content: '' } }],
  },
  tool: {
    title: t('workflowEditor.nodePalette.tool.title'),
    description: t('workflowEditor.nodePalette.tool.description'),
    tool_type: '',
    provider_id: '',
    tool_id: '',
    params: {},
    inputs: [],
    outputs: [{ name: 'text', type: 'string', value: { type: 'generated', content: '' } }],
    meta: {
      type: 'api_tool',
      provider: { id: '', name: '', label: '', icon: '', description: '' },
      tool: { id: '', name: '', label: '', description: '', params: {} },
    },
  },
  dataset_retrieval: {
    title: t('workflowEditor.nodePalette.datasetRetrieval.title'),
    description: t('workflowEditor.nodePalette.datasetRetrieval.description'),
    dataset_ids: [],
    retrieval_config: {
      retrieval_strategy: 'semantic',
      k: 4,
      score: 0,
    },
    inputs: [
      {
        name: 'query',
        type: 'string',
        value: { type: 'ref', content: { ref_node_id: '', ref_var_name: '' } },
      },
    ],
    outputs: [
      { name: 'combine_documents', type: 'string', value: { type: 'generated', content: '' } },
    ],
    meta: { datasets: [] },
  },
  template_transform: {
    title: t('workflowEditor.nodePalette.templateTransform.title'),
    description: t('workflowEditor.nodePalette.templateTransform.description'),
    template: '',
    inputs: [],
    outputs: [{ name: 'output', type: 'string', value: { type: 'generated', content: '' } }],
  },
  http_request: {
    title: t('workflowEditor.nodePalette.httpRequest.title'),
    description: t('workflowEditor.nodePalette.httpRequest.description'),
    url: '',
    method: 'get',
    inputs: [],
    outputs: [
      { name: 'status_code', type: 'int', value: { type: 'generated', content: 0 } },
      { name: 'text', type: 'string', value: { type: 'generated', content: '' } },
    ],
  },
  code: {
    title: t('workflowEditor.nodePalette.code.title'),
    description: t('workflowEditor.nodePalette.code.description'),
    code: '',
    inputs: [],
    outputs: [],
  },
  text_processor: {
    title: t('workflowEditor.nodePalette.textProcessor.title'),
    description: t('workflowEditor.nodePalette.textProcessor.description'),
    mode: 'trim',
    inputs: [{ name: 'text', type: 'string', value: { type: 'literal', content: '' } }],
    outputs: [
      { name: 'output', type: 'string', value: { type: 'generated', content: '' } },
      { name: 'length', type: 'int', value: { type: 'generated', content: 0 } },
    ],
  },
  variable_assigner: {
    title: t('workflowEditor.nodePalette.variableAssigner.title'),
    description: t('workflowEditor.nodePalette.variableAssigner.description'),
    inputs: [{ name: 'value', type: 'string', value: { type: 'literal', content: '' } }],
    outputs: [{ name: 'value', type: 'string', value: { type: 'generated', content: '' } }],
  },
  parameter_extractor: {
    title: t('workflowEditor.nodePalette.parameterExtractor.title'),
    description: t('workflowEditor.nodePalette.parameterExtractor.description'),
    mode: 'auto',
    inputs: [{ name: 'text', type: 'string', value: { type: 'literal', content: '' } }],
    outputs: [{ name: 'param', type: 'string', required: true, value: { type: 'generated', content: '' } }],
  },
  if_else: {
    title: t('workflowEditor.nodePalette.ifElse.title'),
    description: t('workflowEditor.nodePalette.ifElse.description'),
    logical_operator: 'and',
    conditions: [],
    inputs: [],
    outputs: [{ name: 'result', type: 'boolean', value: { type: 'generated', content: false } }],
  },
  end: {
    title: t('workflowEditor.nodePalette.end.title'),
    description: t('workflowEditor.nodePalette.end.description'),
    outputs: [],
  },
}))
const isInitializing = ref(true) // 数据是否初始化
const {
  onPaneReady, // 面板加载完毕事件
  onViewportChange, // 视口变化回调函数
  onConnect, // 边连接回调函数
  onPaneClick, // 工作流面板点击事件
  onNodeClick, // 节点点击事件
  onEdgeClick, // 边点击事件
  onNodeDragStop, // 节点拖动停止回调函数
  findNode, // 根据id查找节点
  nodes: allNodes, // 所有节点
} = useVueFlow()
const { loading: getWorkflowLoading, workflow, loadWorkflow } = useGetWorkflow()
const {
  loading: updateDraftGraphLoading,
  handleUpdateDraftGraph,
  convertGraphToReq,
} = useUpdateDraftGraph()
const { nodes, edges, loadDraftGraph } = useGetDraftGraph()
const { loading: publishWorkflowLoading, handlePublishWorkflow } = usePublishWorkflow()
const { handleCancelPublish } = useCancelPublishWorkflow()
const { loading: shareWorkflowLoading, handleShareWorkflow } = useShareWorkflow()
const {
  forkLoading,
  headerBackRoute,
  workflowStatusText,
  showPreviewReadonlyTag,
  showDebugPassedTag,
  showDebugPendingTag,
  autoSavedTimeText,
  handleAddToMySpace,
} = useWorkflowHeader({
  isPreviewMode,
  workflowId,
  workflow,
  router,
})
const {
  shareActionLabel,
  canOperatePublishedActions,
  handleUpdatePublish,
  handleUpdateConfig,
  handleToggleShare,
  handleCancelPublishAction,
} = useWorkflowPublishActions({
  workflow,
  handlePublishWorkflow,
  handleShareWorkflow,
  loadWorkflow,
  handleCancelPublish,
})

// 定义调试成功后的处理函数
const handleDebugSuccess = async () => {
  // 延迟重新加载 workflow 数据，确保后端已更新 is_debug_passed 状态
  setTimeout(async () => {
    await loadWorkflow(workflowId.value)
  }, 500)
}

const NODE_DEFAULT_TEXTS: Record<
  string,
  { titles: string[]; descriptions: string[] }
> = {
  start: {
    titles: ['开始节点', 'Start Node'],
    descriptions: [
      '工作流的起点节点，支持定义工作流的起点输入等信息',
      'The workflow entry node, used to define the workflow input and related information.',
    ],
  },
  llm: {
    titles: ['大语言模型', 'Large Language Model'],
    descriptions: [
      '调用大语言模型，根据输入参数和提示词生成回复。',
      'Call an LLM to generate a reply based on the input parameters and prompt.',
    ],
  },
  tool: {
    titles: ['扩展插件', 'Plugin'],
    descriptions: [
      '调用插件广场或自定义API插件，支持能力扩展和复用',
      'Call marketplace or custom API plugins to extend and reuse capabilities.',
    ],
  },
  dataset_retrieval: {
    titles: ['知识库检索', 'Knowledge Search'],
    descriptions: [
      '根据输入的参数，在选定的知识库中检索相关片段并召回，返回切片列表',
      'Retrieve relevant chunks from the selected knowledge base based on the input parameters.',
    ],
  },
  template_transform: {
    titles: ['模板转换', 'Template Transform'],
    descriptions: ['对多个字符串变量的格式进行处理', 'Process the format of multiple string variables.'],
  },
  http_request: {
    titles: ['HTTP请求', 'HTTP Request'],
    descriptions: ['配置外部API服务，并发起请求。', 'Configure an external API service and send a request.'],
  },
  code: {
    titles: ['Python代码执行', 'Python Code'],
    descriptions: ['编写代码，处理输入输出变量来生成返回值', 'Write code to process input and output variables and generate a result.'],
  },
  text_processor: {
    titles: ['文本处理', 'Text Processing'],
    descriptions: [
      '对输入文本执行去空格、大小写等常见处理',
      'Perform common text cleanup operations such as trimming and case conversion.',
    ],
  },
  variable_assigner: {
    titles: ['变量赋值', 'Assign Variable'],
    descriptions: [
      '设置变量值，可直接填写字面量或引用上游节点变量',
      'Set variable values with literals or references to upstream nodes.',
    ],
  },
  parameter_extractor: {
    titles: ['参数提取', 'Parameter Extraction'],
    descriptions: [
      '从文本中提取结构化字段，支持 JSON 和 key=value 格式',
      'Extract structured fields from text. Supports JSON and key=value formats.',
    ],
  },
  if_else: {
    titles: ['条件分支', 'Condition Branch'],
    descriptions: ['根据条件判断结果选择不同的执行路径', 'Choose different execution paths based on the condition result.'],
  },
  end: {
    titles: ['结束节点', 'End Node'],
    descriptions: [
      '工作流的结束节点，支持定义工作流最终输出的变量等信息',
      'The workflow exit node, used to define final output variables.',
    ],
  },
}

const syncBuiltInNodeDisplayText = () => {
  allNodes.value.forEach((node) => {
    const nodeType = String(node.type || '')
    const defaults = NODE_DEFAULT_TEXTS[nodeType]
    const localizedNode = NODE_DATA_MAP.value[nodeType]
    if (!defaults || !localizedNode) return

    const data = (node.data ?? {}) as Record<string, unknown>
    const currentTitle = String(data.title ?? '')
    const currentDescription = String(data.description ?? '')
    const titleMatches =
      !currentTitle ||
      defaults.titles.some((item) => currentTitle === item || currentTitle.startsWith(`${item}_`))
    const descriptionMatches =
      !currentDescription || defaults.descriptions.includes(currentDescription)

    if (titleMatches) {
      data.title = currentTitle.includes('_')
        ? `${String(localizedNode.title)}_${currentTitle.split('_').slice(-1)[0]}`
        : localizedNode.title
    }
    if (descriptionMatches) {
      data.description = localizedNode.description
    }
    node.data = data
  })
}

watch(
  () => [locale.value, allNodes.value.map((node) => `${node.id}:${String(node.data?.title ?? '')}:${String(node.data?.description ?? '')}`).join('|')],
  () => syncBuiltInNodeDisplayText(),
  { immediate: true },
)

const VARIABLE_NAME_REGEXP = /^[A-Za-z_][A-Za-z0-9_]*$/
const hasInvalidVariableNames = (variables: Array<Record<string, unknown>> = []) => {
  return variables.some((variable) => !VARIABLE_NAME_REGEXP.test(String(variable?.name ?? '')))
}
const isValidHttpUrl = (url: string) => {
  if (!url) return true
  try {
    const parsedUrl = new URL(url)
    return ['http:', 'https:'].includes(parsedUrl.protocol)
  } catch {
    return false
  }
}
const canSaveDraftGraph = () => {
  return nodes.value.every((node) => {
    const data = node.data ?? {}
    if (node.type === 'start') return !hasInvalidVariableNames(data.inputs)
    if (node.type === 'llm') return !hasInvalidVariableNames(data.inputs)
    if (node.type === 'template_transform') return !hasInvalidVariableNames(data.inputs)
    if (node.type === 'code') {
      return !hasInvalidVariableNames(data.inputs) && !hasInvalidVariableNames(data.outputs)
    }
    if (node.type === 'text_processor') return !hasInvalidVariableNames(data.inputs)
    if (node.type === 'variable_assigner') return !hasInvalidVariableNames(data.inputs)
    if (node.type === 'parameter_extractor') {
      return !hasInvalidVariableNames(data.inputs) && !hasInvalidVariableNames(data.outputs)
    }
    if (node.type === 'if_else') return !hasInvalidVariableNames(data.inputs)
    if (node.type === 'http_request') {
      return isValidHttpUrl(String(data.url ?? '')) && !hasInvalidVariableNames(data.inputs)
    }
    if (node.type === 'tool') return !hasInvalidVariableNames(data.inputs)
    if (node.type === 'end') return !hasInvalidVariableNames(data.outputs)
    return true
  })
}

// 草稿图自动保存（防抖）
const saveDraftGraph = async (is_notify: boolean = false) => {
  if (isInitializing.value || isPreviewMode.value) return // 预览模式下不保存
  if (!canSaveDraftGraph()) return
  const isSaved = await handleUpdateDraftGraph(
    workflowId.value,
    convertGraphToReq(nodes.value, edges.value),
    is_notify,
  )
  if (!isSaved) return
  workflow.value.updated_at = Math.floor(Date.now() / 1000)
}
const debounceSaveDraftGraph = debounce(() => {
  void saveDraftGraph(false)
}, 800)
const triggerDraftGraphSave = (immediate: boolean = false, is_notify: boolean = false) => {
  if (isInitializing.value) return
  if (immediate) {
    debounceSaveDraftGraph.cancel()
    void saveDraftGraph(is_notify)
    return
  }
  debounceSaveDraftGraph()
}

const {
  selectedNode,
  nodeInfoVisible,
  isDebug,
  clearCanvasSelection,
  openNodePanel,
  enterDebugMode,
  onUpdateNode,
} = useWorkflowNodeSidebar({
  nodes,
  triggerDraftGraphSave: () => triggerDraftGraphSave(),
})

const {
  zoomLevel,
  zoomOptions,
  autoLayout,
  addNode,
  onChange,
  handleConnect,
  handlePaneClick,
  handleEdgeClick,
  handleNodeClick,
  handleNodeDragStop,
  handlePaneReady,
  handleViewportChange,
  handleZoomSelect,
} = useWorkflowCanvasInteraction({
  nodes,
  edges,
  allNodes,
  findNode: (id) => (id ? findNode(id) : undefined),
  isPreviewMode,
  isInitializing,
  nodeDataMap: NODE_DATA_MAP,
  triggerDraftGraphSave: () => triggerDraftGraphSave(),
  onPreviewEditBlocked: () => Message.info(t('workflowEditor.previewEditBlocked')),
  onCanvasSelectionClear: clearCanvasSelection,
  onNodeSelected: openNodePanel,
})

onConnect((connection) => {
  handleConnect(connection)
})

onPaneClick(() => {
  handlePaneClick()
})

onEdgeClick(() => {
  handleEdgeClick()
})

onNodeClick((nodeMouseEvent) => {
  handleNodeClick(nodeMouseEvent)
})

onNodeDragStop(() => {
  handleNodeDragStop()
})

onPaneReady((vueFlowInstance) => {
  handlePaneReady(vueFlowInstance)
})

onViewportChange((viewportTransform) => {
  handleViewportChange(viewportTransform)
})

// 页面DOM挂载完毕后加载数据
onMounted(async () => {
  workflowId.value = String(route.params?.workflow_id ?? '')
  await loadWorkflowDetailByMode({
    workflowId: workflowId.value,
    isPreviewMode: isPreviewMode.value,
    workflow: workflow,
    nodes: nodes,
    edges: edges,
    loadWorkflow,
    loadDraftGraph,
    onError: (message: string) => Message.error(message),
  })

  isInitializing.value = false
})

onBeforeUnmount(() => {
  debounceSaveDraftGraph.flush()
  debounceSaveDraftGraph.cancel()
})
</script>

<template>
  <!-- 外部容器 -->
  <div class="w-screen h-screen flex flex-col overflow-hidden relative">
    <!-- 顶部Header -->
    <div
      class="h-[77px] flex-shrink-0 bg-white p-4 flex items-center justify-between relative border-b"
    >
      <!-- 左侧工作流信息 -->
      <div class="flex items-center gap-2">
        <!-- 回退按钮 -->
        <router-link :to="headerBackRoute">
          <a-button size="mini">
            <template #icon>
              <icon-left />
            </template>
          </a-button>
        </router-link>
        <!-- 工作流容器 -->
        <div class="flex items-center gap-3">
          <!-- 工作流图标 -->
          <a-avatar :size="40" shape="square" class="rounded-lg" :image-url="workflow.icon" />
          <!-- 工作流信息 -->
          <div class="flex flex-col justify-between h-[40px]">
            <a-skeleton-line v-if="getWorkflowLoading" :widths="[100]" />
            <div v-else class="text-gray-700 font-bold">{{ workflow.name }}</div>
            <div v-if="getWorkflowLoading" class="flex items-center gap-2">
              <a-skeleton-line :widths="[60]" :line-height="18" />
              <a-skeleton-line :widths="[60]" :line-height="18" />
              <a-skeleton-line :widths="[60]" :line-height="18" />
            </div>
            <div v-else class="flex items-center gap-2">
              <div class="max-w-[160px] line-clamp-1 text-xs text-gray-500">
                {{ workflow.description }}
              </div>
              <div v-if="!isPreviewMode" class="flex items-center h-[18px] text-xs text-gray-500">
                <icon-schedule />
                {{ workflowStatusText }}
              </div>
              <a-tag
                v-if="showPreviewReadonlyTag"
                size="small"
                class="rounded h-[18px] leading-[18px] bg-blue-100 text-blue-700"
              >
                <icon-eye />
                {{ t('workflowEditor.previewMode') }}
              </a-tag>
                <a-tag
                  v-if="showDebugPassedTag"
                  size="small"
                  class="rounded h-[18px] leading-[18px] bg-green-100 text-green-700"
                >
                  <icon-check-circle />
                {{ t('appStudio.shell.debuggedPassed') }}
                </a-tag>
                <a-tag
                  v-if="showDebugPendingTag"
                  size="small"
                  class="rounded h-[18px] leading-[18px] bg-orange-100 text-orange-700"
                >
                  <icon-exclamation-circle />
                {{ t('appStudio.shell.notDebugged') }}
                </a-tag>
              <a-tag v-if="!isPreviewMode" size="small" class="rounded h-[18px] leading-[18px] bg-gray-200 text-gray-500">
                {{ t('appStudio.shell.autoSavedAt', { time: autoSavedTimeText }) }}
              </a-tag>
            </div>
          </div>
        </div>
      </div>
      <!-- 右侧操作按钮 -->
      <div class="">
        <a-space :size="12">
          <!-- 预览模式：显示"添加到我的个人空间"按钮 -->
          <a-button
            v-if="isPreviewMode"
            type="primary"
            :loading="forkLoading"
            @click="handleAddToMySpace"
          >
            <template #icon><icon-plus /></template>
            {{ t('appStudio.shell.personalSpace') }}
          </a-button>

          <!-- 编辑模式：发布按钮组 -->
          <a-button-group v-else>
            <a-button
              :loading="publishWorkflowLoading || shareWorkflowLoading"
              type="primary"
              class="!rounded-tl-lg !rounded-bl-lg"
              @click="handleUpdatePublish"
            >
              {{ t('appStudio.shell.publishUpdate') }}
            </a-button>
            <a-dropdown position="br">
              <a-button
                type="primary"
                class="!rounded-tr-lg !rounded-br-lg !w-5"
              >
                <template #icon>
                  <icon-down />
                </template>
              </a-button>
              <template #content>
                <a-doption
                  @click="handleUpdateConfig"
                >
                  {{ t('appStudio.shell.publishConfigOnly') }}
                </a-doption>
                <a-doption
                  :disabled="!canOperatePublishedActions"
                  @click="handleToggleShare"
                >
                  {{ shareActionLabel }}
                </a-doption>
                <a-doption
                  :disabled="!canOperatePublishedActions"
                  class="!text-red-700"
                  @click="handleCancelPublishAction"
                >
                  {{ t('appStudio.shell.cancelPublish') }}
                </a-doption>
              </template>
            </a-dropdown>
          </a-button-group>
        </a-space>
      </div>
    </div>
    <!-- 中间编排画布 -->
    <div class="flex-1 w-full h-full">
      <vue-flow
        :min-zoom="0.25"
        :max-zoom="2"
        :nodes-connectable="!isPreviewMode"
        :connection-mode="ConnectionMode.Strict"
        :connection-line-options="{ style: { strokeWidth: 2, stroke: '#9ca3af' } }"
        :node-types="NOTE_TYPES"
        v-model:nodes="nodes"
        v-model:edges="edges"
        @update:nodes="onChange"
        @update:edges="onChange"
      >
        <!-- 工作流背景 -->
        <background />
        <!-- 迷你地图 -->
        <mini-map
          class="rounded-xl border border-gray-300 overflow-hidden !left-0 !right-auto"
          :width="160"
          :height="96"
          pannable
          zoomable
        />
        <!-- 使用默认插槽添加工具菜单 -->
        <panel position="bottom-center">
          <div class="p-[5px] bg-white rounded-xl border z-50">
            <a-space :size="8">
              <template #split>
                <a-divider direction="vertical" class="m-0" />
              </template>
              <!-- 添加节点 -->
              <a-trigger
                position="top"
                :popup-translate="[0, -16]"
                :disabled="isPreviewMode"
              >
                <a-button
                  type="primary"
                  size="small"
                  class="rounded-lg px-2"
                  :disabled="isPreviewMode"
                >
                  <template #icon>
                    <icon-plus-circle-fill />
                  </template>
                  {{ t('workflowEditor.addNodeButton') }}
                </a-button>
                <template #content>
                  <div
                    class="bg-white border border-gray-200 w-[520px] shadow rounded-xl overflow-hidden p-3 max-h-[600px] overflow-y-auto"
                  >
                    <!-- 网格布局：2列 -->
                    <div class="grid grid-cols-2 gap-2">
                      <!-- 开始节点 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('start')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-blue-700 rounded-lg flex-shrink-0">
                            <icon-home />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.start.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.start.description') }}
                        </div>
                      </div>

                      <!-- 大语言模型节点 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('llm')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-sky-500 rounded-lg flex-shrink-0">
                            <icon-language />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.llm.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.llm.description') }}
                        </div>
                      </div>

                      <!-- 扩展插件 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('tool')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-orange-500 rounded-lg flex-shrink-0">
                            <icon-tool />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.tool.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.tool.description') }}
                        </div>
                      </div>

                      <!-- 知识库检索 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('dataset_retrieval')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-violet-500 rounded-lg flex-shrink-0">
                            <icon-storage />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.datasetRetrieval.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.datasetRetrieval.description') }}
                        </div>
                      </div>

                      <!-- 模板转换 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('template_transform')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-emerald-400 rounded-lg flex-shrink-0">
                            <icon-branch />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.templateTransform.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.templateTransform.description') }}
                        </div>
                      </div>

                      <!-- HTTP请求 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('http_request')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-rose-500 rounded-lg flex-shrink-0">
                            <icon-link />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.httpRequest.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.httpRequest.description') }}
                        </div>
                      </div>

                      <!-- Python代码执行 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('code')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-cyan-500 rounded-lg flex-shrink-0">
                            <icon-code />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.code.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.code.description') }}
                        </div>
                      </div>

                      <!-- 文本处理 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('text_processor')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-teal-500 rounded-lg flex-shrink-0">
                            <icon-branch />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.textProcessor.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.textProcessor.description') }}
                        </div>
                      </div>

                      <!-- 变量赋值 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('variable_assigner')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-lime-600 rounded-lg flex-shrink-0">
                            <icon-branch />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.variableAssigner.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.variableAssigner.description') }}
                        </div>
                      </div>

                      <!-- 参数提取 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('parameter_extractor')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-indigo-500 rounded-lg flex-shrink-0">
                            <icon-branch />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.parameterExtractor.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.parameterExtractor.description') }}
                        </div>
                      </div>

                      <!-- 条件分支 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('if_else')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-amber-500 rounded-lg flex-shrink-0">
                            <icon-branch />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.ifElse.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.ifElse.description') }}
                        </div>
                      </div>

                      <!-- 结束节点 -->
                      <div
                        class="flex flex-col p-3 gap-2 cursor-pointer hover:bg-gray-50 rounded-lg border border-transparent hover:border-gray-200 transition-all"
                        @click="() => addNode('end')"
                      >
                        <div class="flex items-center gap-2">
                          <a-avatar shape="square" :size="24" class="bg-red-700 rounded-lg flex-shrink-0">
                            <icon-filter />
                          </a-avatar>
                          <div class="text-gray-700 font-semibold text-sm">{{ t('workflowEditor.nodePalette.end.title') }}</div>
                        </div>
                        <div class="text-gray-500 text-xs line-clamp-2">
                          {{ t('workflowEditor.nodePalette.end.description') }}
                        </div>
                      </div>
                    </div>
                  </div>
                </template>
              </a-trigger>
              <!-- 自适应布局&视口大小 -->
              <div class="flex items-center gap-3">
                <a-tooltip :content="t('appStudio.detail.autoLayout')">
                  <a-button
                    size="small"
                    type="text"
                    class="!text-gray-700 rounded-lg"
                    @click="() => autoLayout()"
                  >
                    <template #icon>
                      <icon-apps />
                    </template>
                  </a-button>
                </a-tooltip>
                <a-dropdown
                  trigger="hover"
                  @select="handleZoomSelect"
                >
                  <a-button size="small" class="!text-gray-700 px-2 rounded-lg gap-1 w-[80px]">
                {{ (zoomLevel * 100).toFixed(0) }}%
                    <icon-down />
                  </a-button>
                  <template #content>
                    <a-doption v-for="zoom in zoomOptions" :key="zoom.value" :value="zoom.value">
                      {{ zoom.label }}
                    </a-doption>
                  </template>
                </a-dropdown>
              </div>
              <!-- 调试与预览 -->
              <a-button
                type="text"
                size="small"
                class="px-2 rounded-lg"
                :disabled="isPreviewMode"
                @click="enterDebugMode"
              >
                <template #icon>
                  <icon-play-arrow />
                </template>
                {{ t('workflowEditor.debugTitle') }}
              </a-button>
            </a-space>
          </div>
        </panel>
        <!-- 调试与预览窗口 -->
        <debug-modal
          :workflow_id="workflowId"
          v-model:visible="isDebug"
          @debug-success="handleDebugSuccess"
        />
        <!-- 节点信息容器 -->
        <start-node-info
          v-if="selectedNode && selectedNode?.type === 'start'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
        <llm-node-info
          v-if="selectedNode && selectedNode?.type === 'llm'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
        <template-transform-node-info
          v-if="selectedNode && selectedNode?.type === 'template_transform'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
        <code-node-info
          v-if="selectedNode && selectedNode?.type === 'code'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
        <text-processor-node-info
          v-if="selectedNode && selectedNode?.type === 'text_processor'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
        <variable-assigner-node-info
          v-if="selectedNode && selectedNode?.type === 'variable_assigner'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
        <parameter-extractor-node-info
          v-if="selectedNode && selectedNode?.type === 'parameter_extractor'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
        <if-else-node-info
          v-if="selectedNode && selectedNode?.type === 'if_else'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
        <http-request-node-info
          v-if="selectedNode && selectedNode?.type === 'http_request'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
        <dataset-retrieval-node-info
          v-if="selectedNode && selectedNode?.type === 'dataset_retrieval'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
        <tool-node-info
          v-if="selectedNode && selectedNode?.type === 'tool'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
        <end-node-info
          v-if="selectedNode && selectedNode?.type === 'end'"
          :loading="updateDraftGraphLoading"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
          @update-node="onUpdateNode"
        />
      </vue-flow>
    </div>
  </div>
</template>

<style>
.vue-flow__node.workflow-debug-succeeded > div {
  @apply !border-green-500;
}

.vue-flow__node.workflow-debug-succeeded::after {
  content: '✓';
  position: absolute;
  top: -9px;
  right: -9px;
  z-index: 1;
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  border: 2px solid white;
  border-radius: 9999px;
  background: #16a34a;
  color: white;
  font-size: 14px;
  font-weight: 700;
}

.vue-flow__edge.workflow-debug-edge-succeeded .vue-flow__edge-path {
  stroke: #16a34a;
  stroke-width: 3;
}

.selected {
  .vue-flow__edge-path {
    @apply !stroke-blue-700;
  }
}
</style>
