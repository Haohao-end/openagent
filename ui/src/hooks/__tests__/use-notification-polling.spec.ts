import { flushPromises, mount } from '@vue/test-utils'
import { h } from 'vue'
import { expect, it, vi } from 'vitest'

import { useAgentNotificationPolling } from '@/hooks/use-agent-notification-polling'
import { useDocumentIndexNotificationPolling } from '@/hooks/use-document-index-notification-polling'

const mocks = vi.hoisted(() => ({ getNotifications: vi.fn() }))

vi.mock('@/services/notification', () => ({
  getNotifications: (...args: unknown[]) => mocks.getNotifications(...args),
}))

it.each([
  ['document', useDocumentIndexNotificationPolling, { dataset_id: 'dataset', document_id: 'document', is_read: false }],
  ['agent', useAgentNotificationPolling, { app_id: 'app', app_name: 'Agent', is_read: false }],
])('does not deliver an in-flight %s notification after polling stops', async (_kind, usePolling, notification) => {
  let resolveRequest!: (value: unknown) => void
  mocks.getNotifications.mockReturnValue(new Promise((resolve) => { resolveRequest = resolve }))
  const callback = vi.fn()
  let stopPolling = () => {}
  const wrapper = mount({
    setup() {
      const polling = usePolling() as any
      stopPolling = polling.stopPolling
      polling.startPolling(callback)
      return () => h('div')
    },
  })

  stopPolling()
  resolveRequest({ list: [notification] })
  await flushPromises()

  expect(callback).not.toHaveBeenCalled()
  wrapper.unmount()
})
