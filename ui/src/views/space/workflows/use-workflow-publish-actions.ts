import { computed, type Ref } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { i18n } from '@/i18n'
import { getErrorMessage } from '@/utils/error'
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

const showUnDebugPublishConfirm = (
  t: typeof i18n.global.t,
  { content, onConfirm }: ConfirmPublishOptions,
) => {
  Modal.warning({
    title: t('appStudio.shell.workflowNotDebuggedTitle'),
    content,
    hideCancel: false,
    okText: t('appStudio.shell.confirmPublish'),
    cancelText: t('common.actions.cancel'),
    onOk: async () => {
      await onConfirm()
    },
  })
}

export const useWorkflowPublishActions = (options: UseWorkflowPublishActionsOptions) => {
  const t = i18n.global.t
  const locale = i18n.global.locale as unknown as { value: string }
  const shareActionLabel = computed(() => {
    void locale.value
    return isPublicWorkflow(options.workflow.value)
      ? t('appStudio.shell.unshareFromSquare')
      : t('appStudio.shell.shareToSquare')
  })

  const canOperatePublishedActions = computed(() => {
    return String(options.workflow.value.status || '') === 'published'
  })

  const publishWorkflow = async (shareToSquare: boolean, successMessage: string) => {
    const workflowId = buildWorkflowId(options.workflow.value)
    if (!workflowId) return

    try {
      await options.handlePublishWorkflow(workflowId)

      if (shareToSquare && !isPublicWorkflow(options.workflow.value)) {
        await options.handleShareWorkflow(workflowId, true)
      }

      await options.loadWorkflow(workflowId)
      Message.success(successMessage)
    } catch (error: unknown) {
      // 发布失败需要显式提示，否则按钮点击后无任何反馈
      Message.error(getErrorMessage(error, t('appStudio.shell.workflowActionFailed')))
    }
  }

  const handleUpdatePublish = async () => {
    if (isDebugPassed(options.workflow.value)) {
      await publishWorkflow(true, t('appStudio.shell.workflowPublishedToSquare'))
      return
    }

    showUnDebugPublishConfirm(t, {
      content: t('appStudio.shell.workflowNotDebuggedContent'),
      onConfirm: async () => {
        await publishWorkflow(true, t('appStudio.shell.workflowPublishedToSquare'))
      },
    })
  }

  const handleUpdateConfig = async () => {
    if (isDebugPassed(options.workflow.value)) {
      await publishWorkflow(false, t('appStudio.shell.workflowConfigUpdated'))
      return
    }

    showUnDebugPublishConfirm(t, {
      content: t('appStudio.shell.workflowNotDebuggedContentConfigOnly'),
      onConfirm: async () => {
        await publishWorkflow(false, t('appStudio.shell.workflowConfigUpdated'))
      },
    })
  }

  const handleToggleShare = async () => {
    const workflowId = buildWorkflowId(options.workflow.value)
    if (!workflowId) return

    try {
      await options.handleShareWorkflow(workflowId, !isPublicWorkflow(options.workflow.value))
      await options.loadWorkflow(workflowId)
    } catch {
      return
    }
  }

  const handleCancelPublishAction = async () => {
    const workflowId = buildWorkflowId(options.workflow.value)
    if (!workflowId) return
    try {
      await options.handleCancelPublish(workflowId)
      await options.loadWorkflow(workflowId)
    } catch {
      return
    }
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
