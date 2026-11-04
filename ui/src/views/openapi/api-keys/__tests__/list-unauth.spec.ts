import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import ApiKeysListView from '@/views/openapi/api-keys/ListView.vue'

const mocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  loadApiKeys: vi.fn(),
  handleUpdateApiKeyIsActive: vi.fn(),
  handleDeleteApiKey: vi.fn(),
  credentialState: { credential: { access_token: '', expire_at: 0 } },
  apiKeys: { value: [] as Array<{ id: string }> },
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
  mocks.apiKeys = ref([] as Array<{ id: string }>)
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
