import { mount } from '@vue/test-utils'
import { h } from 'vue'
import { expect, it, vi } from 'vitest'
import { useGetAppAnalysis } from '@/hooks/use-analysis'

const mocks = vi.hoisted(() => ({ getAppAnalysis: vi.fn() }))
vi.mock('@/services/analysis', () => ({ getAppAnalysis: mocks.getAppAnalysis }))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise })
  return { promise, resolve }
}

it('keeps the latest app analysis when route requests resolve out of order', async () => {
  const first = deferred<{ data: { app_id: string } }>(), second = deferred<{ data: { app_id: string } }>()
  mocks.getAppAnalysis.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
  let state!: ReturnType<typeof useGetAppAnalysis>
  const wrapper = mount({ setup() { state = useGetAppAnalysis(); return () => h('div') } })
  const oldRequest = state.loadAppAnalysis('app-1'), newRequest = state.loadAppAnalysis('app-2')
  second.resolve({ data: { app_id: 'app-2' } }); await newRequest
  first.resolve({ data: { app_id: 'app-1' } }); await oldRequest
  expect(state.app_analysis.value).toEqual({ app_id: 'app-2' })
  wrapper.unmount()
})
