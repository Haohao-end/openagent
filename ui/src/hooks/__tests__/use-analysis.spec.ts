import { mount } from '@vue/test-utils'
import { h } from 'vue'
import { expect, it, vi } from 'vitest'
import { useGetAppAnalysis } from '@/hooks/use-analysis'

const mocks = vi.hoisted(() => ({ getAppAnalysis: vi.fn(), messageError: vi.fn() }))
vi.mock('@/services/analysis', () => ({ getAppAnalysis: mocks.getAppAnalysis }))
vi.mock('@arco-design/web-vue', () => ({ Message: { error: mocks.messageError } }))
vi.mock('@/i18n', () => ({ i18n: { global: { t: (key: string) => key } } }))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (error: Error) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => { resolve = resolvePromise; reject = rejectPromise })
  return { promise, resolve, reject }
}

it('keeps the latest app analysis when route requests resolve out of order', async () => {
  const first = deferred<{ data: { app_id: string } }>(), second = deferred<{ data: { app_id: string } }>()
  mocks.getAppAnalysis.mockReset().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
  let state!: ReturnType<typeof useGetAppAnalysis>
  const wrapper = mount({ setup() { state = useGetAppAnalysis(); return () => h('div') } })
  const oldRequest = state.loadAppAnalysis('app-1'), newRequest = state.loadAppAnalysis('app-2')
  second.resolve({ data: { app_id: 'app-2' } }); await newRequest
  first.resolve({ data: { app_id: 'app-1' } }); await oldRequest
  expect(state.app_analysis.value).toEqual({ app_id: 'app-2' })
  wrapper.unmount()
})

it('reports the latest failure and ignores an older route failure', async () => {
  const oldRequest = deferred<{ data: { app_id: string } }>(), currentRequest = deferred<{ data: { app_id: string } }>()
  mocks.getAppAnalysis.mockReset().mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(currentRequest.promise)
  mocks.messageError.mockReset()
  let state!: ReturnType<typeof useGetAppAnalysis>
  const wrapper = mount({ setup() { state = useGetAppAnalysis(); return () => h('div') } })
  const oldLoad = state.loadAppAnalysis('app-1'), currentLoad = state.loadAppAnalysis('app-2')

  currentRequest.reject(new Error('current analysis failed'))
  await currentLoad
  oldRequest.reject(new Error('stale analysis failed'))
  await oldLoad

  expect(mocks.messageError).toHaveBeenCalledTimes(1)
  expect(mocks.messageError).toHaveBeenCalledWith('current analysis failed')
  expect(state.loading.value).toBe(false)
  wrapper.unmount()
})
