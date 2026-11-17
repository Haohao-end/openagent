import { describe, expect, it, vi } from 'vitest'
import { useGetLanguageModel, useGetLanguageModels } from '@/hooks/use-language-model'

const mocks = vi.hoisted(() => ({ getLanguageModel: vi.fn(), getLanguageModels: vi.fn() }))

vi.mock('@/services/language-model', () => ({
  getLanguageModel: (...args: unknown[]) => mocks.getLanguageModel(...args),
  getLanguageModels: (...args: unknown[]) => mocks.getLanguageModels(...args),
}))

const defer = () => {
  let resolve!: (value: any) => void
  let reject!: (error: Error) => void
  const promise = new Promise<any>((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}

describe('useGetLanguageModels', () => {
  it('keeps the latest language models when requests resolve out of order', async () => {
    const olderResponse = defer()
    const newerResponse = defer()
    mocks.getLanguageModels.mockReturnValueOnce(olderResponse.promise).mockReturnValueOnce(newerResponse.promise)
    const { language_models, loading, loadLanguageModels } = useGetLanguageModels()

    const olderRequest = loadLanguageModels()
    const newerRequest = loadLanguageModels()
    newerResponse.resolve({ data: [{ name: 'new-model' }] })
    await newerRequest
    olderResponse.resolve({ data: [{ name: 'old-model' }] })
    const oldResult = await olderRequest

    expect(language_models.value).toEqual([{ name: 'new-model' }])
    expect(oldResult).toBe(false)
    expect(loading.value).toBe(false)
  })

  it('ignores a stale models error after a newer request succeeds', async () => {
    const olderResponse = defer()
    const newerResponse = defer()
    mocks.getLanguageModels.mockReturnValueOnce(olderResponse.promise).mockReturnValueOnce(newerResponse.promise)
    const { language_models, loading, loadLanguageModels } = useGetLanguageModels()

    const olderRequest = loadLanguageModels()
    const newerRequest = loadLanguageModels()
    newerResponse.resolve({ data: [{ name: 'new-model' }] })
    await newerRequest

    olderResponse.reject(new Error('stale models error'))
    await expect(olderRequest).resolves.toBe(false)
    expect(language_models.value).toEqual([{ name: 'new-model' }])
    expect(loading.value).toBe(false)
  })

  it('propagates the latest error and clears loading', async () => {
    const error = new Error('models error')
    mocks.getLanguageModels.mockRejectedValueOnce(error)
    const { loading, loadLanguageModels } = useGetLanguageModels()

    await expect(loadLanguageModels()).rejects.toBe(error)
    expect(loading.value).toBe(false)
  })
})

describe('useGetLanguageModel', () => {
  it('keeps the latest model details when requests resolve out of order', async () => {
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
