import { defineComponent, nextTick, reactive } from 'vue'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDocumentIndexNotificationWebSocket } from '@/hooks/use-document-index-notification-websocket'

const { socketInstance, timeoutEmit, handlers, ioMock } = vi.hoisted(() => {
  const timeoutEmit = vi.fn()
  const handlers = new Map<string, (...args: any[]) => void>()
  const socketInstance = {
    connected: false,
    auth: {},
    on: vi.fn(),
    emit: vi.fn(),
    timeout: vi.fn(),
    disconnect: vi.fn(),
    connect: vi.fn(),
  }
  const ioMock = vi.fn(() => socketInstance)

  return { socketInstance, timeoutEmit, handlers, ioMock }
})

vi.mock('socket.io-client', () => ({
  default: ioMock,
  io: ioMock,
}))

const credentialState = reactive({
  credential: {
    access_token: 'token-1',
    expire_at: Math.floor(Date.now() / 1000) + 3600,
  },
})

vi.mock('@/stores/credential', () => ({
  useCredentialStore: () => credentialState,
}))

const createHarness = () =>
  mount(
    defineComponent({
      setup() {
        return useDocumentIndexNotificationWebSocket()
      },
      template: '<div />',
    }),
  )

describe('useDocumentIndexNotificationWebSocket', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    handlers.clear()
    credentialState.credential = {
      access_token: 'token-1',
      expire_at: Math.floor(Date.now() / 1000) + 3600,
    }
    socketInstance.connected = false
    socketInstance.auth = {}
    socketInstance.on.mockImplementation((event: string, handler: (...args: any[]) => void) => {
      handlers.set(event, handler)
      return socketInstance
    })
    socketInstance.emit.mockImplementation(() => socketInstance)
    socketInstance.timeout.mockReturnValue({ emit: timeoutEmit })
    socketInstance.disconnect.mockImplementation(() => {
      socketInstance.connected = false
      handlers.get('disconnect')?.()
    })
    socketInstance.connect.mockImplementation(() => {
      socketInstance.connected = true
      handlers.get('connect')?.()
    })
  })

  it('creates a socket client and subscribes after connect', async () => {
    const wrapper = createHarness()

    expect(ioMock).toHaveBeenCalledWith(
      'http://localhost:5001',
      expect.objectContaining({
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
      }),
    )

    expect(wrapper.vm.isEnabled).toBe(true)
    expect(wrapper.vm.isConnected).toBe(false)

    socketInstance.connect()
    await nextTick()

    expect(wrapper.vm.isConnected).toBe(true)
    expect(timeoutEmit).toHaveBeenCalledWith(
      'subscribe_document_index_notification',
      expect.any(Function),
    )

    wrapper.unmount()
    expect(socketInstance.disconnect).toHaveBeenCalled()
  })

  it('disconnects when the credential becomes unavailable', async () => {
    const wrapper = createHarness()

    expect(wrapper.vm.isEnabled).toBe(true)

    credentialState.credential = {
      access_token: '',
      expire_at: 0,
    }
    await nextTick()

    expect(wrapper.vm.isEnabled).toBe(false)
    expect(socketInstance.disconnect).toHaveBeenCalled()

    wrapper.unmount()
  })
})
