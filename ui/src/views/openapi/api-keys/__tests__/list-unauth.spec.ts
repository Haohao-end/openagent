import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import ApiKeysListView from '@/views/openapi/api-keys/ListView.vue'

const mocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  loadApiKeys: vi.fn(),
  handleUpdateApiKeyIsActive: vi.fn(),
  handleDeleteApiKey: vi.fn(),
  credentialState: { credential: { access_token: '', expire_at: 0 } },
  apiKeys: { value: [] as Array<{ id: string; is_active?: boolean; expires_at?: number | null; last_used_at?: number | null; scopes?: string[] | null }> },
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
  mocks.apiKeys = ref([] as Array<{ id: string; is_active?: boolean; expires_at?: number | null; last_used_at?: number | null; scopes?: string[] | null }>)
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
  emits: ['change'],
  setup(_, { emit }) { return () => h('button', { 'data-testid': 'api-key-toggle', onClick: () => emit('change', false) }) },
})

describe('openapi api-keys credential state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.credentialState.credential = { access_token: '', expire_at: 0 }
    mocks.apiKeys.value = []
  })

  it('does not request while logged out and isolates keys across account changes', async () => {
    const wrapper = shallowMount(ApiKeysListView, {
      props: {
        create_api_key: false,
      },
      global: {
        stubs: {
          'a-button': buttonStub,
          'a-table': true,
          'a-table-column': true,
          'a-tooltip': true,
          'a-switch': true,
          'icon-user': true,
          'icon-safe': true,
          'icon-plus': true,
          'icon-clock-circle': true,
          'icon-edit': true,
          'icon-delete': true,
          'create-or-update-api-key-modal': true,
        },
      },
    })

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

  it('displays API key metadata with fallbacks for unset values', async () => {
    const wrapper = shallowMount(ApiKeysListView, {
      props: { create_api_key: false },
      global: {
        stubs: {
          'a-button': buttonStub,
          'a-table': tableStub,
          'a-table-column': tableColumnStub,
          'a-tooltip': true,
          'a-switch': true,
          'icon-safe': true,
          'icon-clock-circle': true,
          'icon-edit': true,
          'icon-delete': true,
          'create-or-update-api-key-modal': true,
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
    ]
    await flushPromises()

    expect(wrapper.text()).toContain('2030-01-01')
    expect(wrapper.text()).toContain('2030-01-02 08:00')
    expect(wrapper.text().match(/—/g)).toHaveLength(4)
    expect(wrapper.text()).toContain('openapi:chat')
    expect(wrapper.text()).toContain('无限制（旧密钥）')
    expect(wrapper.text()).toContain('无权限范围')
  })

  it('does not apply a late toggle result to the next account row', async () => {
    const wrapper = shallowMount(ApiKeysListView, {
      props: { create_api_key: false },
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

    const wrapper = shallowMount(ApiKeysListView, {
      props: {
        create_api_key: false,
      },
      global: {
        stubs: {
          'a-button': buttonStub,
          'a-table': true,
          'a-table-column': true,
          'a-tooltip': true,
          'a-switch': true,
          'icon-user': true,
          'icon-safe': true,
          'icon-plus': true,
          'icon-clock-circle': true,
          'icon-edit': true,
          'icon-delete': true,
          'create-or-update-api-key-modal': true,
        },
      },
    })

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
})
