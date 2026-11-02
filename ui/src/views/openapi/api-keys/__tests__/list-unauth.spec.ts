import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import ApiKeysListView from '@/views/openapi/api-keys/ListView.vue'

const mocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  loadApiKeys: vi.fn(),
  handleUpdateApiKeyIsActive: vi.fn(),
  handleDeleteApiKey: vi.fn(),
  credential: { access_token: '', expire_at: 0 },
  apiKeys: [] as Array<Record<string, unknown>>,
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

vi.mock('@/stores/credential', () => ({
  useCredentialStore: () => ({
    credential: mocks.credential,
  }),
}))

vi.mock('@/utils/auth', () => ({
  isCredentialLoggedIn: (credential: { access_token: string; expire_at: number }) =>
    Boolean(credential.access_token) && credential.expire_at > Date.now() / 1000,
}))

vi.mock('@/hooks/use-api-key', async () => {
  const { ref } = await import('vue')
  return {
    useGetApiKeysWithPage: () => ({
      loading: ref(false),
      paginator: ref({
        current_page: 1,
        page_size: 20,
        total_page: 0,
        total_record: 0,
      }),
      api_keys: ref(mocks.apiKeys),
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

describe('openapi api-keys unauthenticated state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.credential.access_token = ''
    mocks.credential.expire_at = 0
    mocks.apiKeys = []
  })

  it('renders login prompt and does not request api keys when user is not logged in', async () => {
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

  it('shows the last-used timestamp and a never-used state for API keys', async () => {
    mocks.credential.access_token = 'valid-token'
    mocks.credential.expire_at = Date.now() / 1000 + 3600
    mocks.apiKeys = [{
      id: 'key-1', api_key: '****************', is_active: true, remark: '',
      created_at: 0, updated_at: 0, last_used_at: 0,
    }]

    const wrapper = shallowMount(ApiKeysListView, {
      props: { create_api_key: false },
      global: {
        stubs: {
          'a-button': buttonStub,
          'a-table': { template: '<div><slot name="columns" /></div>' },
          'a-table-column': {
            props: ['title'],
            data: () => ({ record: { id: 'key-1', api_key: '****************', is_active: true, remark: '', created_at: 0, last_used_at: 0 } }),
            template: '<div><span>{{ title }}</span><slot name="cell" :record="record" /></div>',
          },
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

    expect(wrapper.text()).toContain('最近使用')
    expect(wrapper.text()).toContain('从未使用')
  })
})
