import { computed, ref, type Ref } from 'vue'
import type { RouteLocationRaw, Router } from 'vue-router'
import moment from 'moment/moment'
import { Message } from '@arco-design/web-vue'
import { forkPublicWorkflow } from '@/services/public-workflow'
import { getErrorMessage } from '@/utils/error'

type WorkflowRecord = Record<string, unknown> | null | undefined
type ReadonlyRef<T> = Readonly<Ref<T>>

type UseWorkflowHeaderOptions = {
  isPreviewMode: ReadonlyRef<boolean>
  workflowId: ReadonlyRef<string>
  workflow: ReadonlyRef<WorkflowRecord>
  router: Router
}

const getWorkflowStatus = (workflow: WorkflowRecord): string => {
  return String(workflow?.status || '')
}

const isDebugPassed = (workflow: WorkflowRecord): boolean => {
  return Boolean(workflow?.is_debug_passed)
}

const formatAutoSavedTime = (updatedAt: unknown): string => {
  const timestamp = Number(updatedAt || 0)
  if (!Number.isFinite(timestamp) || timestamp <= 0) return '--:--:--'
  return moment(timestamp * 1000).format('HH:mm:ss')
}

const buildWorkflowId = (workflowId: string): string => {
  return String(workflowId || '').trim()
}

export const useWorkflowHeader = (options: UseWorkflowHeaderOptions) => {
  const forkLoading = ref(false)

  const headerBackRoute = computed<RouteLocationRaw>(() => {
    return {
      name: options.isPreviewMode.value ? 'store-workflows-list' : 'space-workflows-list',
    }
  })

  const workflowStatusText = computed(() => {
    return getWorkflowStatus(options.workflow.value) === 'published' ? '已发布' : '草稿'
  })

  const showPreviewReadonlyTag = computed(() => options.isPreviewMode.value)

  const showDebugPassedTag = computed(() => {
    return !options.isPreviewMode.value && isDebugPassed(options.workflow.value)
  })

  const showDebugPendingTag = computed(() => {
    return !options.isPreviewMode.value && !isDebugPassed(options.workflow.value)
  })

  const autoSavedTimeText = computed(() => {
    return formatAutoSavedTime(options.workflow.value?.updated_at)
  })

  const handleAddToMySpace = async () => {
    const currentWorkflowId = buildWorkflowId(options.workflowId.value)
    if (!currentWorkflowId) {
      Message.error('工作流ID不存在，无法添加')
      return
    }

    try {
      forkLoading.value = true
      const res = await forkPublicWorkflow(currentWorkflowId)
      Message.success(`已添加到个人空间: ${res.data.name}`)
      await options.router.push({
        name: 'space-workflows-detail',
        params: { workflow_id: res.data.id },
      })
    } catch (error: unknown) {
      Message.error(getErrorMessage(error, '添加失败'))
    } finally {
      forkLoading.value = false
    }
  }

  return {
    forkLoading,
    headerBackRoute,
    workflowStatusText,
    showPreviewReadonlyTag,
    showDebugPassedTag,
    showDebugPendingTag,
    autoSavedTimeText,
    handleAddToMySpace,
  }
}
