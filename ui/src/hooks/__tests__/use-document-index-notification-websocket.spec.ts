import { defineComponent, nextTick, reactive } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { socketInstance, timeoutEmit, handlers, ioMock } = vi.hoisted(() => {
  const timeoutEmit = vi.fn()
  const handlers = new Map<string, (...args: any[]) => void>()
  const socketInstance = {
    connected: false,
    auth: {},
    on: vi.fn(),
    off: vi.fn(),
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

const createHarness = async () => {
  vi.resetModules()
  const { useDocumentIndexNotificationWebSocket } = await import('@/hooks/use-document-index-notification-websocket')

  return mount(
    defineComponent({
      setup() {
        return useDocumentIndexNotificationWebSocket()
      },
      template: '<div />',
    }),
  )
}

describe('useDocumentIndexNotificationWebSocket', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    handlers.clear()
    vi.stubEnv('VITE_API_PREFIX', 'http://localhost:5001')
    credentialState.credential = {
      access_token: 'token-1',
      expire_at: Math.floor(Date.now() / 1000) + 3600,
    }
    socketInstance.connected = false
    socketInstance.auth = {}
    socketInstance.off.mockImplementation(() => socketInstance)
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

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('creates a socket client, becomes ready after ack, and unsubscribes on cleanup', async () => {
    const wrapper = await createHarness()
    wrapper.vm.subscribeToNotifications(vi.fn())

    expect(ioMock).toHaveBeenCalledWith(
      'http://localhost:5001',
      expect.objectContaining({
        path: '/socket.io',
        transports: ['websocket'],
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

    const acknowledgeSubscription = timeoutEmit.mock.calls[0][1]
    acknowledgeSubscription(null, {
      ok: true,
      channel: 'document:channel-1',
    })
    await nextTick()

    expect(wrapper.vm.isReady).toBe(true)

    wrapper.unmount()
    expect(socketInstance.off).toHaveBeenCalledWith('document_index_notification', expect.any(Function))
    expect(socketInstance.emit).toHaveBeenCalledWith('unsubscribe_document_index_notification')
    expect(socketInstance.disconnect).toHaveBeenCalled()
  })

  it('derives a proxied socket.io path when the configured api prefix contains /api', async () => {
    vi.stubEnv('VITE_API_PREFIX', 'https://openllm.cloud/api')

    const wrapper = await createHarness()

    expect(ioMock).toHaveBeenCalledWith(
      'https://openllm.cloud',
      expect.objectContaining({
        path: '/api/socket.io',
        transports: ['websocket'],
      }),
    )

    wrapper.unmount()
  })

  it('refreshes auth and resubscribes when the access token changes', async () => {
    const wrapper = await createHarness()

    socketInstance.connect()
    await nextTick()

    const firstAcknowledgeSubscription = timeoutEmit.mock.calls[0][1]
    firstAcknowledgeSubscription(null, {
      ok: true,
      channel: 'document:channel-1',
    })
    await nextTick()

    credentialState.credential = {
      access_token: 'token-2',
      expire_at: Math.floor(Date.now() / 1000) + 7200,
    }
    await nextTick()

    expect(socketInstance.auth).toEqual({
      token: 'token-2',
    })
    expect(socketInstance.disconnect).toHaveBeenCalledTimes(1)
    expect(socketInstance.connect).toHaveBeenCalledTimes(2)
    expect(timeoutEmit).toHaveBeenCalledTimes(2)

    wrapper.unmount()
  })

  it('stays not ready when the server does not acknowledge the subscription', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const wrapper = await createHarness()

    socketInstance.connect()
    await nextTick()

    const acknowledgeSubscription = timeoutEmit.mock.calls[0][1]
    acknowledgeSubscription(null, {
      ok: false,
      error: 'unauthorized',
    })
    await nextTick()

    expect(wrapper.vm.isReady).toBe(false)
    expect(warnSpy).toHaveBeenCalledWith(
      '[WebSocket] Failed to subscribe document notifications:',
      { ok: false, error: 'unauthorized' },
    )

    warnSpy.mockRestore()
    wrapper.unmount()
  })

  it('disconnects when the credential becomes unavailable', async () => {
    const wrapper = await createHarness()

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
