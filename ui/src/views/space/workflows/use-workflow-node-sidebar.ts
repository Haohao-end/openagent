import { ref, type Ref } from 'vue'

export type WorkflowNodeData = Record<string, unknown>

export type WorkflowNodeLike = {
  id: string
  type?: string
  data?: WorkflowNodeData
}

export type SelectedWorkflowNode = {
  id: string
  type: string
  data: WorkflowNodeData
}

type UseWorkflowNodeSidebarOptions = {
  nodes: Ref<WorkflowNodeLike[]>
  triggerDraftGraphSave: () => void
}

export const useWorkflowNodeSidebar = (options: UseWorkflowNodeSidebarOptions) => {
  const selectedNode = ref<SelectedWorkflowNode | null>(null)
  const nodeInfoVisible = ref(false)
  const isDebug = ref(false)

  const clearCanvasSelection = () => {
    isDebug.value = false
    selectedNode.value = null
  }

  const openNodePanel = (node: SelectedWorkflowNode) => {
    if (!selectedNode.value || selectedNode.value.id !== node.id) {
      selectedNode.value = node
      nodeInfoVisible.value = true
    }
    isDebug.value = false
  }

  const enterDebugMode = () => {
    selectedNode.value = null
    isDebug.value = true
  }

  const onUpdateNode = (nodeData: WorkflowNodeData & { id: string }) => {
    const idx = options.nodes.value.findIndex((item) => item.id === nodeData.id)
    if (idx === -1) return

    const currentData = options.nodes.value[idx].data ?? {}
    options.nodes.value[idx].data = {
      ...currentData,
      ...nodeData,
    }

    options.triggerDraftGraphSave()
  }

  return {
    selectedNode,
    nodeInfoVisible,
    isDebug,
    clearCanvasSelection,
    openNodePanel,
    enterDebugMode,
    onUpdateNode,
  }
}
