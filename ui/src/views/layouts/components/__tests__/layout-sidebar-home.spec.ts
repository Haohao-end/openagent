import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LayoutSidebar from '@/views/layouts/components/LayoutSidebar.vue'
import { HOME_NEW_CONVERSATION_QUERY_KEY } from '@/views/pages/home-new-conversation'

const mocks = vi.hoisted(() => ({
  loggedIn: true,
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  route: {
    path: '/space/apps',
    query: {} as Record<string, unknown>,
    params: {} as Record<string, unknown>,
  },
  recentConversations: [] as any[],
  loadRecentConversations: vi.fn(),
  handleDeleteConversation: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({
    push: mocks.routerPush,
    replace: mocks.routerReplace,
  }),
}))

vi.mock('@/stores/credential', () => ({
  useCredentialStore: () => ({
    credential: {},
  }),
}))

vi.mock('@/utils/auth', () => ({
  isCredentialLoggedIn: () => mocks.loggedIn,
}))

vi.mock('@/hooks/use-conversation', async () => {
  const { ref } = await import('vue')
  return {
    useGetRecentConversations: () => ({
      loading: ref(false),
      conversations: ref(mocks.recentConversations),
      loadRecentConversations: mocks.loadRecentConversations,
    }),
    useDeleteConversation: () => ({
      handleDeleteConversation: mocks.handleDeleteConversation,
    }),
  }
})

const slotStub = {
  template: '<div><slot /><slot name="icon" /><slot name="content" /></div>',
}

const mountSidebar = () => {
  return mount(LayoutSidebar, {
    global: {
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a><slot /></a>',
        },
        'a-button': {
          template: '<button type="button"><slot /><slot name="icon" /></button>',
        },
        'a-dropdown': slotStub,
        'a-doption': slotStub,
        'a-skeleton': slotStub,
        'a-skeleton-line': true,
        UpdateConversationNameModal: true,
        IconHome: true,
        IconHomeFull: true,
        IconSpace: true,
        IconSpaceFull: true,
        IconApps: true,
        IconAppsFull: true,
        IconTool: true,
        IconToolFull: true,
        IconStorage: true,
        IconStorageFull: true,
        IconOpenApi: true,
        IconOpenApiFull: true,
        IconMessage: true,
        IconMore: true,
        IconEdit: true,
        IconDelete: true,
      },
    },
  })
}

describe('LayoutSidebar home navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.loggedIn = true
    mocks.route.path = '/space/apps'
    mocks.route.query = {}
    mocks.route.params = {}
    mocks.recentConversations = []
  })

  it('starts a new home conversation when a logged-in user clicks Home', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(1710835200000)

    const wrapper = mountSidebar()
    await flushPromises()

    await wrapper.get('[data-testid="sidebar-home-new-conversation"]').trigger('click')

    expect(mocks.routerPush).toHaveBeenCalledWith({
      path: '/home',
      query: {
        [HOME_NEW_CONVERSATION_QUERY_KEY]: '1710835200000',
      },
    })
  })

  it('keeps anonymous Home clicks as plain home navigation', async () => {
    mocks.loggedIn = false

    const wrapper = mountSidebar()
    await flushPromises()

    await wrapper.get('[data-testid="sidebar-home-new-conversation"]').trigger('click')

    expect(mocks.routerPush).toHaveBeenCalledWith('/home')
  })
})
