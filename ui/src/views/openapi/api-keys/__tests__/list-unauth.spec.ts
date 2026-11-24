import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { Message } from '@arco-design/web-vue'
import ApiKeysListView from '@/views/openapi/api-keys/ListView.vue'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  loadApiKeys: vi.fn(),
  handleUpdateApiKeyIsActive: vi.fn(),
  handleDeleteApiKey: vi.fn(),
  credentialState: { credential: { access_token: '', expire_at: 0 } },
  apiKeys: { value: [] as Array<{ id: string; is_active?: boolean; expires_at?: number | null; last_used_at?: number | null; scopes?: string[] | null; request_count?: number | null }> },
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({
      fullPath: '/openapi/api-keys',
      path: '/openapi/api-keys',
      query: {},
    }),
    useRouter: () => ({
      push: mocks.routerPush,
    }),
  }
})

vi.mock('@/stores/credential', async () => {
  const { reactive } = await import('vue')
  const state = reactive(mocks.credentialState)
  mocks.credentialState = state
  return { useCredentialStore: () => state }
})

vi.mock('@/hooks/use-api-key', async () => {
  const { ref } = await import('vue')
  mocks.apiKeys = ref([] as Array<{ id: string; is_active?: boolean; expires_at?: number | null; last_used_at?: number | null; scopes?: string[] | null; request_count?: number | null }>)
  return {
    useGetApiKeysWithPage: () => ({
      loading: ref(false),
      paginator: ref({
        current_page: 1,
        page_size: 20,
        total_page: 0,
        total_record: 0,
      }),
      api_keys: mocks.apiKeys,
      loadApiKeys: mocks.loadApiKeys,
    }),
    useUpdateApiKeyIsActive: () => ({
      handleUpdateApiKeyIsActive: mocks.handleUpdateApiKeyIsActive,
    }),
    useDeleteApiKey: () => ({
      handleDeleteApiKey: mocks.handleDeleteApiKey,
    }),
  }
})

const buttonStub = {
  template: '<button v-bind="$attrs" @click="$emit(\'click\')"><slot /></button>',
}
const tableStub = { template: '<div><slot name="columns" /></div>' }
const tableColumnStub = defineComponent({
  setup(_, { slots }) { return () => h('div', mocks.apiKeys.value.map((record, rowIndex) => slots.cell?.({ record, rowIndex }))) },
})
const switchStub = defineComponent({
  props: ['loading', 'disabled', 'modelValue'],
  emits: ['change'],
  setup(props, { emit }) {
    return () =>
      h('button', {
        'data-testid': 'api-key-toggle',
        'data-loading': String(props.loading),
        'data-disabled': String(props.disabled),
        onClick: () => {
          if (!props.disabled) emit('change', false)
        },
      })
  },
})

const baseStubs = {
  'a-button': buttonStub,
  'a-table': true,
  'a-table-column': true,
  'a-tooltip': { template: '<div><slot /></div>' },
  'a-switch': true,
  'icon-user': true,
  'icon-safe': true,
  'icon-plus': true,
  'icon-clock-circle': true,
  'icon-edit': true,
  'icon-delete': true,
  'create-or-update-api-key-modal': true,
}

const mountView = (options: { props?: Record<string, any>; global?: Record<string, any> } = {}) => shallowMount(ApiKeysListView, {
  props: { create_api_key: false, ...options.props },
  global: {
    ...options.global,
    stubs: {
      ...baseStubs,
      ...options.global?.stubs,
    },
  },
})

describe('openapi api-keys credential state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.credentialState.credential = { access_token: '', expire_at: 0 }
    mocks.apiKeys.value = []
  })

  it('does not request while logged out and isolates keys across account changes', async () => {
    const wrapper = mountView()

    await flushPromises()

    expect(wrapper.text()).toContain('请先登录')
    expect(wrapper.text()).toContain('登录后即可查看、创建和管理您的 API 密钥')
    expect(mocks.loadApiKeys).not.toHaveBeenCalled()

    mocks.loadApiKeys.mockImplementationOnce(() => { mocks.apiKeys.value = [{ id: 'user-a-key' }] })
    mocks.credentialState.credential = { access_token: 'token-a', expire_at: 4102444800 }
    await flushPromises()
    mocks.credentialState.credential = { access_token: 'token-b', expire_at: 4102444800 }
    await flushPromises()

    expect(mocks.apiKeys.value).toEqual([])
    expect(mocks.loadApiKeys).toHaveBeenCalledTimes(2)
  })

  it('displays metadata, expired status, and keys without recorded use', async () => {
    const wrapper = mountView({
      global: {
        stubs: {
          'a-table': tableStub,
          'a-table-column': tableColumnStub,
        },
      },
    })
    await flushPromises()
    mocks.credentialState.credential = { access_token: 'token', expire_at: 4102444800 }
    await flushPromises()
    mocks.apiKeys.value = [
      { id: 'scoped', is_active: true, expires_at: 1893456000, last_used_at: 1893542400, scopes: ['openapi:chat'] },
      { id: 'legacy', is_active: true, expires_at: 0, last_used_at: 0, scopes: null },
      { id: 'no-scopes', is_active: true, scopes: [] },
      { id: 'expired', is_active: true, expires_at: 1, last_used_at: 0 },
    ]
    await flushPromises()

    expect(wrapper.text()).toContain('2030-01-01')
    expect(wrapper.text()).toContain('2030-01-02 08:00')
    expect(wrapper.text().match(/—/g)).toHaveLength(2)
    expect(wrapper.text()).toContain('openapi:chat')
    expect(wrapper.text()).toContain('无限制（旧密钥）')
    expect(wrapper.text()).toContain('无权限范围')
    expect(wrapper.text()).toContain('已过期')
    expect(wrapper.text()).toContain('暂无使用记录')
  })

  it('displays cumulative request count, falls back to 0 for unused or legacy keys, and hides raw secret', async () => {
    const wrapper = mountView({
      global: {
        stubs: {
          'a-table': tableStub,
          'a-table-column': tableColumnStub,
        },
      },
    })
    await flushPromises()
    mocks.credentialState.credential = { access_token: 'token', expire_at: 4102444800 }
    await flushPromises()
    mocks.apiKeys.value = [
      { id: 'used-key', is_active: true, request_count: 128 },
      { id: 'unused-key', is_active: true, request_count: 0 },
      { id: 'legacy-key', is_active: true },
      { id: 'null-count-key', is_active: true, request_count: null },
    ]
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('128')
    // 未使用或缺失 request_count 的 Key 均展示 0
    expect(text).toContain('0')
    // 列表不显示任何敏感原始密钥（如 sk-xxx）
    expect(text).not.toContain('sk-')
    expect(text).not.toContain('secret')
  })

  it('updates an active key to expired when its expiration time arrives', async () => {
    vi.useFakeTimers()
    const expiresAt = 1893456000
    vi.setSystemTime(expiresAt * 1000 - 1000)
    mocks.credentialState.credential = { access_token: 'token', expire_at: 4102444800 }
    const wrapper = mountView({
      global: { stubs: { 'a-table': tableStub, 'a-table-column': tableColumnStub, 'a-switch': switchStub } },
    })

    try {
      mocks.apiKeys.value = [{ id: 'expires-soon', is_active: true, expires_at: expiresAt }]
      await flushPromises()
      expect(wrapper.text()).toContain('可用')

      await vi.advanceTimersByTimeAsync(1000)
      await flushPromises()
      expect(wrapper.text()).toContain('已过期')
    } finally {
      wrapper.unmount()
      vi.useRealTimers()
    }
  })

  it('does not apply a late toggle result to the next account row', async () => {
    const wrapper = mountView({
      global: { stubs: { 'a-table': tableStub, 'a-table-column': tableColumnStub, 'a-switch': switchStub } },
    })
    mocks.credentialState.credential = { access_token: 'token-a', expire_at: 4102444800 }
    await flushPromises()
    mocks.apiKeys.value = [{ id: 'user-a-key', is_active: true }]
    await flushPromises()
    let finishUpdate!: () => void
    mocks.handleUpdateApiKeyIsActive.mockImplementationOnce((_id, _value, callback) => { finishUpdate = callback })
    await wrapper.find('[data-testid="api-key-toggle"]').trigger('click')
    mocks.credentialState.credential = { access_token: 'token-b', expire_at: 4102444800 }
    await flushPromises()
    mocks.apiKeys.value = [{ id: 'user-b-key', is_active: true }]
    finishUpdate()
    expect(mocks.apiKeys.value).toEqual([{ id: 'user-b-key', is_active: true }])
  })

  it('dispatches auth-required event when clicking login button', async () => {
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent')

    const wrapper = mountView()

    await flushPromises()
    await wrapper.find('button').trigger('click')

    const authRequiredEvents = dispatchSpy.mock.calls
      .map((call) => call[0] as Event)
      .filter((event) => event.type === 'llmops:auth-required') as CustomEvent<{
      redirect: string
    }>[]

    expect(authRequiredEvents.length).toBeGreaterThan(0)
    expect(authRequiredEvents.at(-1)?.detail).toEqual({ redirect: '/openapi/api-keys' })

    dispatchSpy.mockRestore()
  })

  it('shows the backend error and unlocks the switch when toggling fails', async () => {
    const errorSpy = vi.spyOn(Message, 'error').mockImplementation(() => undefined as never)
    mocks.handleUpdateApiKeyIsActive.mockRejectedValueOnce(new Error('toggle failed'))

    const wrapper = mountView({
      global: { stubs: { 'a-table': tableStub, 'a-table-column': tableColumnStub, 'a-switch': switchStub } },
    })
    mocks.credentialState.credential = { access_token: 'token-a', expire_at: 4102444800 }
    await flushPromises()
    mocks.apiKeys.value = [{ id: 'key-1', is_active: true }]
    await flushPromises()

    const toggle = wrapper.find('[data-testid="api-key-toggle"]')
    await toggle.trigger('click')
    await flushPromises()

    expect(errorSpy).toHaveBeenCalledWith('toggle failed')
    expect(toggle.attributes('data-loading')).toBe('false')
    expect(toggle.attributes('data-disabled')).toBe('false')
    errorSpy.mockRestore()
  })

  it('locks the switch with loading state during update to prevent duplicate requests', async () => {
    let resolveUpdate!: () => void
    const updatePromise = new Promise<void>((resolve) => {
      resolveUpdate = resolve
    })
    mocks.handleUpdateApiKeyIsActive.mockImplementationOnce(() => updatePromise)

    const wrapper = mountView({
      global: { stubs: { 'a-table': tableStub, 'a-table-column': tableColumnStub, 'a-switch': switchStub } },
    })
    mocks.credentialState.credential = { access_token: 'token-a', expire_at: 4102444800 }
    await flushPromises()
    mocks.apiKeys.value = [{ id: 'key-1', is_active: true }]
    await flushPromises()

    const toggle = wrapper.find('[data-testid="api-key-toggle"]')
    await toggle.trigger('click')

    expect(mocks.handleUpdateApiKeyIsActive).toHaveBeenCalledTimes(1)
    expect(toggle.attributes('data-loading')).toBe('true')
    expect(toggle.attributes('data-disabled')).toBe('true')

    await toggle.trigger('click')
    expect(mocks.handleUpdateApiKeyIsActive).toHaveBeenCalledTimes(1)

    resolveUpdate()
    await flushPromises()
    expect(toggle.attributes('data-loading')).toBe('false')
  })
})
