import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
const { getHistories } = vi.hoisted(() => ({ getHistories: vi.fn() }))
vi.mock('@/services/app', async (original) => ({
  ...(await original<typeof import('@/services/app')>()), getPublishHistoriesWithPage: getHistories,
}))
import PublishHistoryDrawer from '../PublishHistoryDrawer.vue'
const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  return { promise: new Promise<T>((done, fail) => { resolve = done; reject = fail }), resolve, reject }
}
const response = (version: number) => ({ data: {
  list: [{ id: `history-${version}`, version, created_at: 0 }],
  paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
} })
const app = (id: string) => ({ id, name: id, icon: '', description: '', draft_updated_at: 0 })
const stub = { template: '<div><slot /></div>' }
const mountDrawer = (errorHandler?: (error: unknown) => void) => mount(PublishHistoryDrawer, {
  props: { visible: false, app: app('app-a') },
  global: {
    config: { errorHandler },
    stubs: Object.fromEntries(['a-drawer', 'a-spin', 'a-card', 'a-tag', 'a-space'].map((name) => [name, stub])),
  },
})
it('reloads for a new app and ignores stale requests after app changes and reopen', async () => {
  const pending = Array.from({ length: 4 }, () => deferred<ReturnType<typeof response>>())
  pending.forEach(({ promise }) => getHistories.mockReturnValueOnce(promise))
  const wrapper = mountDrawer()
  await wrapper.setProps({ visible: true }); await wrapper.setProps({ app: app('app-b') })
  await flushPromises()
  expect(getHistories.mock.calls.map(([id]) => id)).toEqual(['app-a', 'app-b'])
  pending[1].resolve(response(2)); await flushPromises()
  pending[0].resolve(response(1)); await flushPromises()
  expect(wrapper.text()).toContain('# 002')
  expect(wrapper.text()).not.toContain('# 001')
  for (const visible of [false, true, false, true]) await wrapper.setProps({ visible })
  expect(getHistories).toHaveBeenCalledTimes(4)
  pending[3].resolve(response(4)); await flushPromises()
  pending[2].resolve(response(3)); await flushPromises()
  expect(wrapper.text()).toContain('# 004')
  expect(wrapper.text()).not.toContain('# 003')
  wrapper.unmount()
})

it('does not surface a stale history request failure after switching apps', async () => {
  getHistories.mockReset()
  const older = deferred<ReturnType<typeof response>>()
  const newer = deferred<ReturnType<typeof response>>()
  getHistories.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
  const errors: unknown[] = []
  const wrapper = mountDrawer((error) => errors.push(error))
  await wrapper.setProps({ visible: true }); await flushPromises()
  await wrapper.setProps({ app: app('app-b') }); await flushPromises()
  newer.resolve(response(2)); await flushPromises()
  older.reject(new Error('stale history failure')); await flushPromises()

  expect(errors).toEqual([])
  expect(wrapper.text()).toContain('# 002')
  wrapper.unmount()
})
