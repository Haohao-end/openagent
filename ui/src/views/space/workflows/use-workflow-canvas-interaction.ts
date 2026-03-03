import { v4 } from 'uuid'
import dagre from 'dagre'
import { cloneDeep } from 'lodash'
import { ref, type Ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { generateRandomString } from '@/utils/helper'
import type { SelectedWorkflowNode, WorkflowNodeData, WorkflowNodeLike } from '@/views/space/workflows/use-workflow-node-sidebar'

type FlowEdge = Record<string, unknown> & {
  source?: string
  target?: string
  sourceHandle?: string | null
  targetHandle?: string | null
}

type FlowNode = WorkflowNodeLike & {
  position: { x: number; y: number }
  dimensions?: { width?: number; height?: number }
}

type FlowBooleanState = {
  value: boolean
}

type NodeDataMap = Record<string, WorkflowNodeData>

type ConnectionLike = {
  source?: string
  target?: string
  sourceHandle?: string | null
  targetHandle?: string | null
}

type NodeMouseEventLike = {
  node: {
    id: string
    type?: string
    data?: WorkflowNodeData
  }
}

type ViewportTransformLike = {
  zoom: number
}

type FlowInstanceLike = {
  fitView: (options?: { padding?: number; duration?: number }) => void
  zoomTo: (value: number) => void
}

type UseWorkflowCanvasInteractionOptions = {
  nodes: Ref<FlowNode[]>
  edges: Ref<FlowEdge[]>
  allNodes: Ref<FlowNode[]>
  findNode: (id: string | null | undefined) => FlowNode | undefined
  isPreviewMode: FlowBooleanState
  isInitializing: FlowBooleanState
  nodeDataMap: NodeDataMap
  triggerDraftGraphSave: () => void
  onPreviewEditBlocked: () => void
  onCanvasSelectionClear: () => void
  onNodeSelected: (node: SelectedWorkflowNode) => void
}

export const useWorkflowCanvasInteraction = (options: UseWorkflowCanvasInteractionOptions) => {
  const instance = ref<FlowInstanceLike | null>(null)
  const zoomLevel = ref<number>(1)
  const zoomOptions = [
    { label: '200%', value: 2 },
    { label: '100%', value: 1 },
    { label: '75%', value: 0.75 },
    { label: '50%', value: 0.5 },
    { label: '25%', value: 0.25 },
  ]

  const autoLayout = () => {
    const dagreGraph = new dagre.graphlib.Graph()
    dagreGraph.setDefaultEdgeLabel(() => ({}))
    dagreGraph.setGraph({
      rankdir: 'LR',
      align: 'UL',
      nodesep: 80,
      ranksep: 60,
      edgesep: 10,
    })

    const cloneNodes = cloneDeep(options.nodes.value)
    const cloneEdges = cloneDeep(options.edges.value)

    cloneNodes.forEach((node) => {
      dagreGraph.setNode(node.id, {
        width: Number(node.dimensions?.width || 0),
        height: Number(node.dimensions?.height || 0),
      })
    })

    cloneEdges.forEach((edge) => {
      dagreGraph.setEdge(String(edge.source || ''), String(edge.target || ''))
    })

    dagre.layout(dagreGraph)

    options.nodes.value = cloneNodes.map((node) => {
      const layoutedNode = dagreGraph.node(node.id) as { x?: number; y?: number } | undefined
      return {
        ...node,
        position: {
          x: Number(layoutedNode?.x ?? node.position.x),
          y: Number(layoutedNode?.y ?? node.position.y),
        },
      }
    })
  }

  const addNode = (nodeType: string) => {
    if (options.isPreviewMode.value) {
      Message.warning('预览模式下无法编辑，请先添加到个人空间')
      return
    }

    if (nodeType === 'start' && options.allNodes.value.some((node) => node.type === 'start')) {
      Message.error('工作流中只允许有一个开始节点')
      return
    }

    if (nodeType === 'end' && options.allNodes.value.some((node) => node.type === 'end')) {
      Message.error('工作流中只允许有一个结束节点')
      return
    }

    const nodeCount = options.allNodes.value.length
    const total = options.allNodes.value.reduce(
      (acc, item) => {
        acc.xSum += item.position.x
        acc.ySum += item.position.y
        return acc
      },
      { xSum: 0, ySum: 0 },
    )

    const xAverage = nodeCount > 0 ? total.xSum / nodeCount : 0
    const yAverage = nodeCount > 0 ? total.ySum / nodeCount : 0

    const nodeData = cloneDeep(options.nodeDataMap[nodeType])
    if (!nodeData) return

    options.nodes.value.push({
      id: v4(),
      type: nodeType,
      position: { x: xAverage, y: yAverage },
      data: {
        ...nodeData,
        title: `${String(nodeData.title || nodeType)}_${generateRandomString(5)}`,
      },
    })
  }

  const onChange = () => {
    if (options.isInitializing.value) return
    options.triggerDraftGraphSave()
  }

  const handleConnect = (connection: ConnectionLike) => {
    const { source, target, sourceHandle } = connection
    if (!source || !target) return

    if (source === target) {
      Message.error('不能将节点连接到本身')
      return
    }

    const sourceNode = options.findNode(source)
    if (sourceNode?.type === 'if_else' && !sourceHandle) {
      Message.error('条件分支节点必须从绿叉（True）或红叉（False）连接')
      return
    }

    const isAlreadyConnected = options.edges.value.some((edge) => {
      if (edge.source === source && edge.target === target) {
        if (sourceHandle || edge.sourceHandle) {
          return edge.sourceHandle === sourceHandle
        }
        return true
      }
      if (edge.source === target && edge.target === source) {
        return true
      }
      return false
    })

    if (isAlreadyConnected) {
      Message.error('这两个节点已有连接，无需重复添加')
      return
    }

    const targetNode = options.findNode(target)
    const { sourceHandle: sh, targetHandle: th, ...connectionRest } = connection

    const label =
      sourceNode?.type === 'if_else' ? (sh === 'true' ? 'True' : 'False') : undefined

    options.edges.value.push({
      ...connectionRest,
      id: v4(),
      source_type: sourceNode?.type,
      target_type: targetNode?.type,
      source_handle: sh || null,
      target_handle: th || null,
      sourceHandle: sh || undefined,
      targetHandle: th || undefined,
      label,
      animated: true,
      style: { strokeWidth: 2, stroke: '#9ca3af' },
      source,
      target,
    })
  }

  const handlePaneClick = () => {
    options.onCanvasSelectionClear()
  }

  const handleEdgeClick = () => {
    options.onCanvasSelectionClear()
  }

  const handleNodeClick = (nodeMouseEvent: NodeMouseEventLike) => {
    if (options.isPreviewMode.value) {
      options.onPreviewEditBlocked()
      return
    }

    const selectedNode: SelectedWorkflowNode = {
      id: nodeMouseEvent.node.id,
      type: String(nodeMouseEvent.node.type || ''),
      data: nodeMouseEvent.node.data || {},
    }
    options.onNodeSelected(selectedNode)
  }

  const handleNodeDragStop = () => {
    if (options.isPreviewMode.value) return
    options.triggerDraftGraphSave()
  }

  const handlePaneReady = (vueFlowInstance: FlowInstanceLike) => {
    vueFlowInstance.fitView()
    instance.value = vueFlowInstance
  }

  const handleViewportChange = (viewportTransform: ViewportTransformLike) => {
    zoomLevel.value = viewportTransform.zoom
  }

  const handleZoomSelect = (value: string | number) => {
    zoomLevel.value = Number(value)
    instance.value?.zoomTo(Number(value))
  }

  return {
    instance,
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
  }
}
