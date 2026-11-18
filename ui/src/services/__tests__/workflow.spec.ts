import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getWorkflowResultTrace } from '@/services/workflow'
import * as request from '@/utils/request'

vi.mock('@/utils/request', () => ({
  get: vi.fn(),
  post: vi.fn(),
  ssePost: vi.fn(),
}))

describe('workflow service result trace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(request.get).mockResolvedValue({
      code: 'success',
      data: {
        id: 'res-1',
        workflow_id: 'wf-1',
        status: 'succeeded',
        latency: 0.88,
        created_at: 1700000000,
        updated_at: 1700000001,
        steps: [],
      },
    } as never)
  })

  it('fetches workflow result trace timeline details by workflow and result id', async () => {
    const result = await getWorkflowResultTrace('wf-1', 'res-1')

    expect(request.get).toHaveBeenCalledWith('/workflows/wf-1/results/res-1/trace')
    expect(result.data.id).toBe('res-1')
  })
})
