import { shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import AgentBindingsAbilityItem from '../AgentBindingsAbilityItem.vue'

const mocks = vi.hoisted(() => ({ update: vi.fn() }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  return { useUpdateDraftAppConfig: () => ({ loading: ref(false), handleUpdateDraftAppConfig: mocks.update }) }
})
vi.mock('@arco-design/web-vue', () => ({ Message: { warning: vi.fn(), success: vi.fn() } }))

it('includes an earlier agent selection when a second save overlaps', async () => {
  let resolveFirst!: () => void
  const firstSave = new Promise<void>((resolve) => { resolveFirst = resolve })
  mocks.update.mockReset().mockReturnValueOnce(firstSave).mockResolvedValue({})
  const wrapper = shallowMount(AgentBindingsAbilityItem, { props: { app_id: 'app-1', agent_bindings: [] } })
  const state = (wrapper.vm.$ as any).setupState
  const first = { app_id: 'agent-1', name: 'First', source_scope: 'public' }
  const second = { app_id: 'agent-2', name: 'Second', source_scope: 'public' }
  const firstSelection = state.handleSelectMarketplaceBinding(first)
  const secondSelection = state.handleSelectMarketplaceBinding(second)
  await Promise.resolve()
  const requestsWhileFirstSavePending = mocks.update.mock.calls.length
  resolveFirst()
  await Promise.all([firstSelection, secondSelection])
  const secondRequest = mocks.update.mock.calls[1]?.[1].agent_bindings.map((item: any) => item.app_id)
  expect(requestsWhileFirstSavePending).toBe(1)
  expect(secondRequest).toEqual(['agent-1', 'agent-2'])
  expect(state.activateAgentBindings.map((item: any) => item.app_id)).toEqual(['agent-1', 'agent-2'])
  wrapper.unmount()
})
