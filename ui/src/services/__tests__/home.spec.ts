import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getHomeIntent } from '@/services/home'
import * as request from '@/utils/request'

vi.mock('@/utils/request', () => ({
  get: vi.fn(),
}))

describe('home service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(request.get).mockResolvedValue({ data: {} } as never)
  })

  it('loads home intent from the home intent endpoint', async () => {
    await getHomeIntent()

    expect(request.get).toHaveBeenCalledWith('/home/intent')
  })
})
