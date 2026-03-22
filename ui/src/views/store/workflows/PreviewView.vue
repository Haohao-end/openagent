<script setup lang="ts">
import { markRaw, onMounted, ref, nextTick, provide, defineAsyncComponent, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ConnectionMode, Panel, useVueFlow, VueFlow, type Edge, type Node } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { MiniMap } from '@vue-flow/minimap'
import { Message } from '@arco-design/web-vue'
import { getPublicWorkflowDetail } from '@/services/public-workflow'
import { getErrorMessage } from '@/utils/error'
import StartNode from '@/views/space/workflows/components/nodes/StartNode.vue'
import LlmNode from '@/views/space/workflows/components/nodes/LLMNode.vue'
import DatasetRetrievalNode from '@/views/space/workflows/components/nodes/DatasetRetrievalNode.vue'
import CodeNode from '@/views/space/workflows/components/nodes/CodeNode.vue'
import HttpRequestNode from '@/views/space/workflows/components/nodes/HttpRequestNode.vue'
import ToolNode from '@/views/space/workflows/components/nodes/ToolNode.vue'
import TemplateTransformNode from '@/views/space/workflows/components/nodes/TemplateTransformNode.vue'
import EndNode from '@/views/space/workflows/components/nodes/EndNode.vue'
import TextProcessorNode from '@/views/space/workflows/components/nodes/TextProcessorNode.vue'
import VariableAssignerNode from '@/views/space/workflows/components/nodes/VariableAssignerNode.vue'
import ParameterExtractorNode from '@/views/space/workflows/components/nodes/ParameterExtractorNode.vue'
import IfElseNode from '@/views/space/workflows/components/nodes/IfElseNode.vue'
import { getPublicWorkflowDraftGraph } from '@/services/public-workflow'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/minimap/dist/style.css'

// 导入节点信息组件
import StartNodeInfo from '@/views/space/workflows/components/infos/StartNodeInfo.vue'
import LlmNodeInfo from '@/views/space/workflows/components/infos/LLMNodeInfo.vue'
import TemplateTransformNodeInfo from '@/views/space/workflows/components/infos/TemplateTransformNodeInfo.vue'
import TextProcessorNodeInfo from '@/views/space/workflows/components/infos/TextProcessorNodeInfo.vue'
import VariableAssignerNodeInfo from '@/views/space/workflows/components/infos/VariableAssignerNodeInfo.vue'
import ParameterExtractorNodeInfo from '@/views/space/workflows/components/infos/ParameterExtractorNodeInfo.vue'
import IfElseNodeInfo from '@/views/space/workflows/components/infos/IfElseNodeInfo.vue'
import HttpRequestNodeInfo from '@/views/space/workflows/components/infos/HttpRequestNodeInfo.vue'
import DatasetRetrievalNodeInfo from '@/views/space/workflows/components/infos/DatasetRetrievalNodeInfo.vue'
import ToolNodeInfo from '@/views/space/workflows/components/infos/ToolNodeInfo.vue'
import { useWorkflowHeader } from '@/views/space/workflows/use-workflow-header'

const CodeNodeInfo = defineAsyncComponent(
  () => import('@/views/space/workflows/components/infos/CodeNodeInfo.vue'),
)

const route = useRoute()
const router = useRouter()
const workflowId = ref<string>(String(route.params?.workflow_id ?? ''))
const isPreviewMode = ref(true)
const loading = ref(false)
type PreviewWorkflow = {
  id: string
  name: string
  icon: string
  description: string
  account_name: string
  account_avatar: string
  view_count: number
  fork_count: number
  is_debug_passed?: boolean
}
type FlowInstance = {
  fitView: (options?: { padding?: number; duration?: number }) => void
  zoomTo: (value: number) => void
}
type SelectedNode = {
  id: string
  type: string
  data?: Record<string, unknown>
}
const workflow = ref<PreviewWorkflow | null>(null)
const workflowForHeader = computed<Record<string, unknown>>(() => {
  return workflow.value ?? {}
})
const {
  forkLoading,
  headerBackRoute,
  handleAddToMySpace,
} = useWorkflowHeader({
  isPreviewMode,
  workflowId,
  workflow: workflowForHeader,
  router,
})
const instance = ref<FlowInstance | null>(null)
const zoomLevel = ref<number>(1)

// 节点选择和信息面板
const selectedNode = ref<SelectedNode | null>(null)
const nodeInfoVisible = ref(false)

// 提供只读状态给所有子组件
provide('isReadonly', true)

const zoomOptions = [
  { label: '200%', value: 2 },
  { label: '100%', value: 1 },
  { label: '75%', value: 0.75 },
  { label: '50%', value: 0.5 },
  { label: '25%', value: 0.25 },
]

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

const {
  onPaneReady,
  onViewportChange,
  onNodeClick,
  onPaneClick,
  onEdgeClick,
} = useVueFlow()

// 使用普通的 ref，不使用 useVueFlow 的 nodes 和 edges
const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])

// 加载工作流详情
const loadWorkflow = async () => {
  try {
    loading.value = true
    const res = await getPublicWorkflowDetail(workflowId.value)
    workflow.value = res.data
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '加载工作流失败'))
  } finally {
    loading.value = false
  }
}

// 加载工作流图
const loadDraftGraph = async () => {
  try {
    const res = await getPublicWorkflowDraftGraph(workflowId.value)
    const data = res.data

    // 清空现有数据
    nodes.value.splice(0, nodes.value.length)
    edges.value.splice(0, edges.value.length)

    // 处理节点数据 - 确保结构正确
    if (data.nodes && Array.isArray(data.nodes)) {
      data.nodes.forEach((node) => {
        const currentNode = node as Partial<Node>
        // 后端已经转换好了格式，但需要确保所有必需字段都存在
        const processedNode: Node = {
          id: String(currentNode.id || ''),
          type: String(currentNode.type || ''),
          position: currentNode.position || { x: 0, y: 0 },
          data: currentNode.data || {},
        }
        nodes.value.push(processedNode)
      })
    }

    // 处理边数据
    if (data.edges && Array.isArray(data.edges)) {
      data.edges.forEach((edge) => {
        const currentEdge = edge as Partial<Edge>
        const processedEdge: Edge = {
          id: String(currentEdge.id || ''),
          source: String(currentEdge.source || ''),
          target: String(currentEdge.target || ''),
          sourceHandle: currentEdge.sourceHandle || undefined,
          targetHandle: currentEdge.targetHandle || undefined,
          animated: true,
          style: { strokeWidth: 2, stroke: '#9ca3af' },
        }
        edges.value.push(processedEdge)
      })
    }
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '加载工作流图失败'))
  }
}

onPaneReady((vueFlowInstance) => {
  instance.value = vueFlowInstance as FlowInstance
  // 不要在这里调用 fitView，等数据加载完成后再调用
})

onViewportChange((viewportTransform) => {
  zoomLevel.value = viewportTransform.zoom
})

// 节点点击事件 - 显示只读信息面板
onNodeClick((nodeMouseEvent) => {
  if (!selectedNode.value || selectedNode.value?.id !== nodeMouseEvent.node.id) {
    selectedNode.value = nodeMouseEvent.node as SelectedNode
    nodeInfoVisible.value = true
  }
})

// 面板点击事件 - 关闭信息面板
onPaneClick(() => {
  selectedNode.value = null
  nodeInfoVisible.value = false
})

// 边点击事件 - 关闭信息面板
onEdgeClick(() => {
  selectedNode.value = null
  nodeInfoVisible.value = false
})

onMounted(async () => {
  // 先加载工作流基本信息
  await loadWorkflow()

  // 再加载图数据
  await loadDraftGraph()

  // 使用 nextTick 确保 DOM 更新完成
  await nextTick()

  // 等待 Vue Flow 完全初始化后调整视图
  setTimeout(() => {
    if (instance.value && nodes.value.length > 0) {
      try {
        instance.value.fitView({ padding: 0.2, duration: 200 })
      } catch {
        // Ignore fitView failures when graph is not fully laid out yet.
      }
    }
  }, 500)
})
</script>

<template>
  <div class="min-h-screen flex flex-col h-full overflow-hidden relative">
    <!-- 顶部Header -->
    <div class="h-[77px] flex-shrink-0 bg-white p-4 flex items-center justify-between relative border-b">
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
          <a-avatar v-if="workflow" :size="40" shape="square" class="rounded-lg" :image-url="workflow.icon" />
          <a-skeleton v-else shape="square" :size="40" />
          <!-- 工作流信息 -->
          <div class="flex flex-col justify-between h-[40px]">
            <a-skeleton-line v-if="loading" :widths="[100]" />
            <div v-else-if="workflow" class="flex items-center gap-2">
              <div class="text-gray-700 font-bold">{{ workflow.name }}</div>
              <a-tag color="orange" size="small">预览模式</a-tag>
            </div>
            <div v-if="loading" class="flex items-center gap-2">
              <a-skeleton-line :widths="[60]" :line-height="18" />
              <a-skeleton-line :widths="[60]" :line-height="18" />
            </div>
            <div v-else-if="workflow" class="flex items-center gap-2">
              <a-avatar :size="20" :image-url="workflow.account_avatar" />
              <div class="flex items-center h-[18px] text-xs text-gray-500">
                <icon-user />
                {{ workflow.account_name }}
              </div>
              <div class="flex items-center h-[18px] text-xs text-gray-500">
                <icon-eye />
                {{ workflow.view_count }} 次浏览
              </div>
              <div class="flex items-center h-[18px] text-xs text-gray-500">
                <icon-branch />
                {{ workflow.fork_count }} 次Fork
              </div>
              <a-tag
                v-if="workflow.is_debug_passed"
                size="small"
                class="rounded h-[18px] leading-[18px] bg-green-100 text-green-700"
              >
                <icon-check-circle />
                已调试通过
              </a-tag>
            </div>
          </div>
        </div>
      </div>
      <!-- 右侧操作按钮 -->
      <div class="">
        <a-button
          :loading="forkLoading"
          type="primary"
          @click="handleAddToMySpace"
        >
          <template #icon>
            <icon-plus />
          </template>
          添加到我的个人空间
        </a-button>
      </div>
    </div>
    <!-- 中间编排画布 -->
    <div class="flex-1">
      <vue-flow
        :min-zoom="0.25"
        :max-zoom="2"
        :nodes-connectable="false"
        :nodes-draggable="false"
        :connection-mode="ConnectionMode.Strict"
        :node-types="NOTE_TYPES"
        v-model:nodes="nodes"
        v-model:edges="edges"
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
              <!-- 视口大小 -->
              <div class="flex items-center gap-3">
                  <a-dropdown
                  trigger="hover"
                  @select="
                    (value: string | number) => {
                      zoomLevel = Number(value)
                      instance?.zoomTo(Number(value))
                    }
                  "
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
            </a-space>
          </div>
        </panel>
      </vue-flow>

      <!-- 节点信息面板（只读模式） - 移到 vue-flow 外部 -->
      <!-- Debug: selectedNode type = {{ selectedNode?.type }}, visible = {{ nodeInfoVisible }} -->
      <start-node-info
        v-if="selectedNode && selectedNode.type === 'start'"
        :loading="false"
        :node="selectedNode"
        v-model:visible="nodeInfoVisible"
      />
      <llm-node-info
        v-if="selectedNode && selectedNode.type === 'llm'"
        :loading="false"
        :node="selectedNode"
        v-model:visible="nodeInfoVisible"
      />
      <template-transform-node-info
        v-if="selectedNode && selectedNode.type === 'template_transform'"
        :loading="false"
        :node="selectedNode"
        v-model:visible="nodeInfoVisible"
      />
      <code-node-info
        v-if="selectedNode && selectedNode.type === 'code'"
        :loading="false"
        :node="selectedNode"
        v-model:visible="nodeInfoVisible"
      />
      <text-processor-node-info
        v-if="selectedNode && selectedNode.type === 'text_processor'"
        :loading="false"
        :node="selectedNode"
        v-model:visible="nodeInfoVisible"
      />
      <variable-assigner-node-info
        v-if="selectedNode && selectedNode.type === 'variable_assigner'"
        :loading="false"
        :node="selectedNode"
        v-model:visible="nodeInfoVisible"
      />
      <parameter-extractor-node-info
        v-if="selectedNode && selectedNode.type === 'parameter_extractor'"
        :loading="false"
        :node="selectedNode"
        v-model:visible="nodeInfoVisible"
      />
      <if-else-node-info
        v-if="selectedNode && selectedNode.type === 'if_else'"
        :loading="false"
        :node="selectedNode"
        v-model:visible="nodeInfoVisible"
      />
      <http-request-node-info
        v-if="selectedNode && selectedNode.type === 'http_request'"
        :loading="false"
        :node="selectedNode"
        v-model:visible="nodeInfoVisible"
      />

      <!-- 使用 Teleport 将 Info 组件传送到 body，避免 DOM 冲突 -->
      <teleport to="body">
        <dataset-retrieval-node-info
          v-if="selectedNode && selectedNode.type === 'dataset_retrieval'"
          :loading="false"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
        />
      </teleport>
      <teleport to="body">
        <tool-node-info
          v-if="selectedNode && selectedNode.type === 'tool'"
          :loading="false"
          :node="selectedNode"
          v-model:visible="nodeInfoVisible"
        />
      </teleport>
    </div>
  </div>
</template>

<style>
.selected {
  .vue-flow__edge-path {
    @apply !stroke-blue-700;
  }
}
</style>
