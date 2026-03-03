import type { Ref } from 'vue'
import { getPublicWorkflowDetail, getPublicWorkflowDraftGraph } from '@/services/public-workflow'
import { getErrorMessage } from '@/utils/error'

type WorkflowDetailLike = {
  id: string
  name: string
  icon: string
  description: string
  status: string
  is_debug_passed: boolean
  is_public: boolean
  updated_at: number
}

type LoadWorkflowDetailOptions = {
  workflowId: string
  isPreviewMode: boolean
  workflow: Ref<Record<string, unknown>>
  nodes: Ref<Array<Record<string, unknown>>>
  edges: Ref<Array<Record<string, unknown>>>
  loadWorkflow: (workflowId: string) => Promise<void>
  loadDraftGraph: (workflowId: string) => Promise<void>
  onError: (message: string) => void
}

const toPreviewWorkflow = (
  workflow: Awaited<ReturnType<typeof getPublicWorkflowDetail>>['data'],
): WorkflowDetailLike => {
  return {
    id: workflow.id,
    name: workflow.name,
    icon: workflow.icon,
    description: workflow.description,
    status: 'published',
    is_debug_passed: true,
    is_public: true,
    updated_at: workflow.created_at,
  }
}

export const loadWorkflowDetailByMode = async (options: LoadWorkflowDetailOptions) => {
  if (options.isPreviewMode) {
    try {
      const [workflowRes, graphRes] = await Promise.all([
        getPublicWorkflowDetail(options.workflowId),
        getPublicWorkflowDraftGraph(options.workflowId),
      ])

      options.workflow.value = toPreviewWorkflow(workflowRes.data)
      options.nodes.value = graphRes.data.nodes || []
      options.edges.value = graphRes.data.edges || []
    } catch (error: unknown) {
      options.onError(getErrorMessage(error, '加载工作流失败'))
    }
    return
  }

  await options.loadWorkflow(options.workflowId)
  await options.loadDraftGraph(options.workflowId)
}
