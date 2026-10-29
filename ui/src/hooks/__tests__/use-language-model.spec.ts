import { describe, expect, it, vi } from 'vitest'
import { useGetLanguageModel } from '@/hooks/use-language-model'

const mocks = vi.hoisted(() => ({ getLanguageModel: vi.fn(), getLanguageModels: vi.fn() }))

vi.mock('@/services/language-model', () => ({
  getLanguageModel: (...args: unknown[]) => mocks.getLanguageModel(...args),
  getLanguageModels: (...args: unknown[]) => mocks.getLanguageModels(...args),
}))

describe('useGetLanguageModel', () => {
  it('keeps the latest model details when requests resolve out of order', async () => {
    const defer = () => {
      let resolve!: (value: any) => void
      const promise = new Promise<any>((done) => { resolve = done })
      return { promise, resolve }
    }
    const olderResponse = defer()
    const newerResponse = defer()
    mocks.getLanguageModel.mockReturnValueOnce(olderResponse.promise).mockReturnValueOnce(newerResponse.promise)
    const { language_model, loadLanguageModel } = useGetLanguageModel()

    const olderRequest = loadLanguageModel('provider', 'old')
    const newerRequest = loadLanguageModel('provider', 'new')
    newerResponse.resolve({ data: { name: 'new' } })
    await newerRequest
    olderResponse.resolve({ data: { name: 'old' } })
    await olderRequest

    expect(language_model.value).toEqual({ name: 'new' })
  })
})
