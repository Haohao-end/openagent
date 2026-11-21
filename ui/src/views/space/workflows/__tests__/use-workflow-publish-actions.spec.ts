import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const messageSuccess = vi.fn()
const messageError = vi.fn()

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: (message: string) => messageSuccess(message),
    error: (message: string) => messageError(message),
  },
  Modal: { warning: vi.fn() },
}))

import { useWorkflowPublishActions } from '@/views/space/workflows/use-workflow-publish-actions'

const buildActions = (overrides: Record<string, unknown> = {}) =>
  useWorkflowPublishActions({
    workflow: ref({ id: 'wf-1', is_debug_passed: true, is_public: false, status: 'published' }),
    handlePublishWorkflow: vi.fn().mockResolvedValue(undefined),
    handleShareWorkflow: vi.fn().mockResolvedValue(undefined),
    loadWorkflow: vi.fn().mockResolvedValue(undefined),
    handleCancelPublish: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as never)

describe('useWorkflowPublishActions error feedback', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('surfaces the publish error instead of silently swallowing it', async () => {
    const { handleUpdatePublish } = buildActions({
      handlePublishWorkflow: vi.fn().mockRejectedValue(new Error('publish failed')),
    })

    await handleUpdatePublish()

    expect(messageError).toHaveBeenCalledWith('publish failed')
    expect(messageSuccess).not.toHaveBeenCalled()
  })

  it('still reports success and refreshes the workflow when publishing works', async () => {
    const loadWorkflow = vi.fn().mockResolvedValue(undefined)
    const { handleUpdatePublish } = buildActions({ loadWorkflow })

    await handleUpdatePublish()

    expect(loadWorkflow).toHaveBeenCalledWith('wf-1')
    expect(messageSuccess).toHaveBeenCalled()
    expect(messageError).not.toHaveBeenCalled()
  })
})
