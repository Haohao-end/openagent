import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGenerateIconPreview, useRegenerateIcon } from '../use-tool'
import * as apiToolService from '@/services/api-tool'

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
  },
  Modal: {
    warning: vi.fn(),
  },
}))

describe('use-tool icon race condition protection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps the latest icon preview when earlier generation completes last', async () => {
    let resolveFirst!: (value: any) => void
    let resolveSecond!: (value: any) => void

    const p1 = new Promise((resolve) => { resolveFirst = resolve })
    const p2 = new Promise((resolve) => { resolveSecond = resolve })

    vi.spyOn(apiToolService, 'generateIconPreview')
      .mockReturnValueOnce(p1 as any)
      .mockReturnValueOnce(p2 as any)

    const { icon, handleGenerateIconPreview } = useGenerateIconPreview()

    const req1 = handleGenerateIconPreview('tool-1', 'desc 1')
    const req2 = handleGenerateIconPreview('tool-2', 'desc 2')

    resolveSecond({ code: 'success', data: { icon: 'https://cdn.example.com/icon-2.png' } })
    await req2
    expect(icon.value).toBe('https://cdn.example.com/icon-2.png')

    resolveFirst({ code: 'success', data: { icon: 'https://cdn.example.com/icon-1.png' } })
    await req1
    expect(icon.value).toBe('https://cdn.example.com/icon-2.png')
  })

  it('keeps the latest regenerated icon when earlier regeneration completes last', async () => {
    let resolveFirst!: (value: any) => void
    let resolveSecond!: (value: any) => void

    const p1 = new Promise((resolve) => { resolveFirst = resolve })
    const p2 = new Promise((resolve) => { resolveSecond = resolve })

    vi.spyOn(apiToolService, 'regenerateIcon')
      .mockReturnValueOnce(p1 as any)
      .mockReturnValueOnce(p2 as any)

    const { icon, handleRegenerateIcon } = useRegenerateIcon()

    const req1 = handleRegenerateIcon('provider-1')
    const req2 = handleRegenerateIcon('provider-2')

    resolveSecond({ code: 'success', data: { icon: 'https://cdn.example.com/regen-2.png' } })
    await req2
    expect(icon.value).toBe('https://cdn.example.com/regen-2.png')

    resolveFirst({ code: 'success', data: { icon: 'https://cdn.example.com/regen-1.png' } })
    await req1
    expect(icon.value).toBe('https://cdn.example.com/regen-2.png')
  })
})
