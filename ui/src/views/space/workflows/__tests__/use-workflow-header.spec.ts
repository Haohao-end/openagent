import { defineComponent, h, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Router } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { useWorkflowHeader } from '@/views/space/workflows/use-workflow-header'

const forkPublicWorkflowMock = vi.fn()
const messageSuccessMock = vi.fn()
const messageErrorMock = vi.fn()

vi.mock('@/services/public-workflow', () => {
  return {
    forkPublicWorkflow: (workflowId: string) => forkPublicWorkflowMock(workflowId),
  }
})

vi.mock('@arco-design/web-vue', () => {
  return {
    Message: {
      success: (message: string) => messageSuccessMock(message),
      error: (message: string) => messageErrorMock(message),
    },
  }
})

vi.mock('@/utils/error', () => {
  return {
    getErrorMessage: () => '添加失败',
  }
})

const createRouter = () => {
  return {
    push: vi.fn().mockResolvedValue(undefined),
  } as unknown as Router
}

describe('use-workflow-header', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('builds header route and tag states by preview mode', () => {
    const isPreviewMode = ref(true)
    const workflowId = ref('workflow-1')
    const workflow = ref<Record<string, unknown>>({
      status: 'draft',
      is_debug_passed: false,
      updated_at: 1700000000,
    })
    const router = createRouter()
    const header = useWorkflowHeader({ isPreviewMode, workflowId, workflow, router })

    expect(header.headerBackRoute.value).toEqual({ name: 'store-workflows-list' })
    expect(header.workflowStatusText.value).toBe('草稿')
    expect(header.showPreviewReadonlyTag.value).toBe(true)
    expect(header.showDebugPassedTag.value).toBe(false)
    expect(header.showDebugPendingTag.value).toBe(false)
    expect(header.autoSavedTimeText.value).toMatch(/^\d{2}:\d{2}:\d{2}$/)

    isPreviewMode.value = false
    workflow.value = {
      ...workflow.value,
      status: 'published',
      is_debug_passed: true,
    }

    expect(header.headerBackRoute.value).toEqual({ name: 'space-workflows-list' })
    expect(header.workflowStatusText.value).toBe('已发布')
    expect(header.showPreviewReadonlyTag.value).toBe(false)
    expect(header.showDebugPassedTag.value).toBe(true)
    expect(header.showDebugPendingTag.value).toBe(false)
  })

  it('forks workflow and redirects to personal detail page', async () => {
    forkPublicWorkflowMock.mockResolvedValue({
      data: { id: 'new-workflow-id', name: '新工作流' },
    })

    const isPreviewMode = ref(true)
    const workflowId = ref('workflow-1')
    const workflow = ref<Record<string, unknown>>({})
    const router = createRouter()
    const header = useWorkflowHeader({ isPreviewMode, workflowId, workflow, router })

    await header.handleAddToMySpace()

    expect(forkPublicWorkflowMock).toHaveBeenCalledWith('workflow-1')
    expect(messageSuccessMock).toHaveBeenCalledWith('已添加到个人空间: 新工作流')
    expect(router.push).toHaveBeenCalledWith({
      name: 'space-workflows-detail',
      params: { workflow_id: 'new-workflow-id' },
    })
    expect(header.forkLoading.value).toBe(false)
  })

  it('blocks fork when workflow id is missing', async () => {
    const isPreviewMode = ref(true)
    const workflowId = ref(' ')
    const workflow = ref<Record<string, unknown>>({})
    const router = createRouter()
    const header = useWorkflowHeader({ isPreviewMode, workflowId, workflow, router })

    await header.handleAddToMySpace()

    expect(forkPublicWorkflowMock).not.toHaveBeenCalled()
    expect(messageErrorMock).toHaveBeenCalledWith('工作流ID不存在，无法添加')
    expect(router.push).not.toHaveBeenCalled()
  })

  it('does not notify or navigate when a workflow fork completes after unmount', async () => {
    let resolveFork!: (value: { data: { id: string; name: string } }) => void
    forkPublicWorkflowMock.mockReturnValueOnce(new Promise((resolve) => { resolveFork = resolve }))
    const router = createRouter()
    const Wrapper = defineComponent({
      setup() {
        const header = useWorkflowHeader({
          isPreviewMode: ref(true), workflowId: ref('workflow-1'), workflow: ref({}), router,
        })
        return () => h('button', { onClick: header.handleAddToMySpace }, 'fork')
      },
    })
    const wrapper = mount(Wrapper)

    await wrapper.get('button').trigger('click')
    await flushPromises()
    wrapper.unmount()
    resolveFork({ data: { id: 'forked-workflow', name: 'Forked workflow' } })
    await flushPromises()

    expect(messageSuccessMock).not.toHaveBeenCalled()
    expect(messageErrorMock).not.toHaveBeenCalled()
    expect(router.push).not.toHaveBeenCalled()
  })
})
