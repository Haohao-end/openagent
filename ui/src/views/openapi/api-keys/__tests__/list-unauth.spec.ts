import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import ApiKeysListView from '@/views/openapi/api-keys/ListView.vue'

const mocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  loadApiKeys: vi.fn(),
  handleUpdateApiKeyIsActive: vi.fn(),
  handleDeleteApiKey: vi.fn(),
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
    credential: {
      access_token: '',
      expire_at: 0,
    },
  }),
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
      api_keys: ref([]),
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
})
