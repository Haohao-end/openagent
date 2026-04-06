import { computed, type Ref } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
type WorkflowRecord = Record<string, unknown>

type UseWorkflowPublishActionsOptions = {
  workflow: Ref<WorkflowRecord>
  handlePublishWorkflow: (workflowId: string) => Promise<unknown>
  handleShareWorkflow: (workflowId: string, isPublic: boolean) => Promise<unknown>
  loadWorkflow: (workflowId: string) => Promise<unknown>
  handleCancelPublish: (workflowId: string) => Promise<unknown> | void
}

type ConfirmPublishOptions = {
  content: string
  onConfirm: () => Promise<void>
}

const buildWorkflowId = (workflow: WorkflowRecord): string => {
  return String(workflow.id || '').trim()
}

const isDebugPassed = (workflow: WorkflowRecord): boolean => {
  return Boolean(workflow.is_debug_passed)
}

const isPublicWorkflow = (workflow: WorkflowRecord): boolean => {
  return Boolean(workflow.is_public)
}

const showUnDebugPublishConfirm = ({ content, onConfirm }: ConfirmPublishOptions) => {
  Modal.warning({
    title: '工作流未调试',
    content,
    hideCancel: false,
    okText: '确认发布',
    cancelText: '取消',
    onOk: async () => {
      await onConfirm()
    },
  })
}

export const useWorkflowPublishActions = (options: UseWorkflowPublishActionsOptions) => {
  const shareActionLabel = computed(() => {
    return isPublicWorkflow(options.workflow.value) ? '取消分享到广场' : '分享到广场'
  })

  const canOperatePublishedActions = computed(() => {
    return String(options.workflow.value.status || '') === 'published'
  })

  const publishWorkflow = async (shareToSquare: boolean, successMessage: string) => {
    const workflowId = buildWorkflowId(options.workflow.value)
    if (!workflowId) return

    await options.handlePublishWorkflow(workflowId)

    if (shareToSquare && !isPublicWorkflow(options.workflow.value)) {
      await options.handleShareWorkflow(workflowId, true)
    }

    await options.loadWorkflow(workflowId)
    Message.success(successMessage)
  }

  const handleUpdatePublish = async () => {
    if (isDebugPassed(options.workflow.value)) {
      await publishWorkflow(true, '工作流已发布到广场')
      return
    }

    showUnDebugPublishConfirm({
      content: '该工作流尚未调试成功，是否确认发布？发布后将更新草稿配置并发布到工作流广场。',
      onConfirm: async () => {
        await publishWorkflow(true, '工作流已发布到广场')
      },
    })
  }

  const handleUpdateConfig = async () => {
    if (isDebugPassed(options.workflow.value)) {
      await publishWorkflow(false, '工作流配置已更新')
      return
    }

    showUnDebugPublishConfirm({
      content: '该工作流尚未调试成功，是否确认发布？发布后将更新草稿配置。',
      onConfirm: async () => {
        await publishWorkflow(false, '工作流配置已更新')
      },
    })
  }

  const handleToggleShare = async () => {
    const workflowId = buildWorkflowId(options.workflow.value)
    if (!workflowId) return

    await options.handleShareWorkflow(workflowId, !isPublicWorkflow(options.workflow.value))
    await options.loadWorkflow(workflowId)
  }

  const handleCancelPublishAction = async () => {
    const workflowId = buildWorkflowId(options.workflow.value)
    if (!workflowId) return
    await options.handleCancelPublish(workflowId)
  }

  return {
    shareActionLabel,
    canOperatePublishedActions,
    handleUpdatePublish,
    handleUpdateConfig,
    handleToggleShare,
    handleCancelPublishAction,
  }
}
