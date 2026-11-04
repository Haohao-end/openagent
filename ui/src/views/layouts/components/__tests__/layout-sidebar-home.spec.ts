import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LayoutSidebar from '@/views/layouts/components/LayoutSidebar.vue'

const mocks = vi.hoisted(() => ({
  loggedIn: true,
  credentialState: { credential: { access_token: 'token-a' } },
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  route: {
    path: '/space/apps',
    query: {} as Record<string, unknown>,
    params: {} as Record<string, unknown>,
  },
  recentConversations: [] as any[],
  recentConversationsRef: undefined as any,
  allRecentConversations: [] as any[],
  loadRecentConversations: vi.fn(),
  invalidateRecentConversations: vi.fn(),
  handleDeleteConversation: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({
    push: mocks.routerPush,
    replace: mocks.routerReplace,
  }),
}))

vi.mock('@/stores/credential', async () => {
  const { reactive } = await import('vue')
  mocks.credentialState = reactive(mocks.credentialState)
  return { useCredentialStore: () => mocks.credentialState }
})

vi.mock('@/utils/auth', () => ({
  isCredentialLoggedIn: () => mocks.loggedIn,
}))

vi.mock('@/hooks/use-conversation', async () => {
  const { ref } = await import('vue')
  if (!mocks.recentConversationsRef) {
    mocks.recentConversationsRef = ref([])
  }
  return {
    useGetRecentConversations: () => ({
      loading: ref(false),
      conversations: mocks.recentConversationsRef,
      loadRecentConversations: mocks.loadRecentConversations,
      invalidateRecentConversations: mocks.invalidateRecentConversations,
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
          template: '<a :data-to="to"><slot /></a>',
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
        IconRelation: {
          template: '<i data-icon="relation"><slot /></i>',
        },
        IconTool: true,
        IconToolFull: true,
        IconStorage: {
          template: '<i data-icon="storage"><slot /></i>',
        },
        IconStorageFull: {
          template: '<i data-icon="storage"><slot /></i>',
        },
        IconComputer: {
          template: '<i data-icon="computer"><slot /></i>',
        },
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

const createRecentConversation = (index: number) => ({
  id: `conversation-${index + 1}`,
  name: `Conversation ${index + 1}`,
  source_type: index % 2 === 0 ? 'assistant_agent' : 'app_debugger',
  app_id: index % 2 === 0 ? '' : `app-${index + 1}`,
  message_id: `message-${index + 1}`,
})

describe('LayoutSidebar home navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.loggedIn = true
    mocks.route.path = '/space/apps'
    mocks.route.query = {}
    mocks.route.params = {}
    mocks.recentConversations.splice(0, mocks.recentConversations.length)
    if (mocks.recentConversationsRef) {
      mocks.recentConversationsRef.value = []
    }
    mocks.allRecentConversations.splice(0, mocks.allRecentConversations.length)
  })

  it('clears recent conversations and reloads when the authenticated credential changes', async () => {
    mocks.loadRecentConversations.mockImplementationOnce(async () => {
      mocks.recentConversationsRef.value = [createRecentConversation(0)]
    })
    const wrapper = mountSidebar()
    const list = wrapper.get('.recent-conversation-list')
    Object.defineProperty(list.element, 'clientHeight', { value: 400 })
    Object.defineProperty(list.element, 'scrollHeight', { value: 500 })
    await flushPromises()
    expect(wrapper.text()).toContain('Conversation 1')

    mocks.credentialState.credential = { access_token: 'token-b' }
    await flushPromises()

    expect(mocks.loadRecentConversations).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('Conversation 1')
    wrapper.unmount()
  })

  it('navigates to plain home when a logged-in user clicks Home', async () => {
    const wrapper = mountSidebar()
    await flushPromises()

    await wrapper.get('[data-testid="sidebar-home-new-conversation"]').trigger('click')

    expect(mocks.routerPush).toHaveBeenCalledWith('/home')
  })

  it('keeps anonymous Home clicks as plain home navigation', async () => {
    mocks.loggedIn = false

    const wrapper = mountSidebar()
    await flushPromises()

    await wrapper.get('[data-testid="sidebar-home-new-conversation"]').trigger('click')

    expect(mocks.routerPush).toHaveBeenCalledWith('/home')
    expect(mocks.invalidateRecentConversations).toHaveBeenCalledTimes(1)
  })

  it('renders the skills and mcp store entries only once', async () => {
    const wrapper = mountSidebar()
    await flushPromises()

    expect(wrapper.findAll('a[data-to="/store/skills"]')).toHaveLength(1)
    expect(wrapper.findAll('a[data-to="/store/mcp"]')).toHaveLength(1)
  })

  it('uses different icons for workflow, skills, and mcp stores', async () => {
    const wrapper = mountSidebar()
    await flushPromises()

    expect(wrapper.findAll('a[data-to="/store/workflows"] [data-icon="relation"]')).toHaveLength(1)
    expect(wrapper.findAll('a[data-to="/store/workflows"] [data-icon="storage"]')).toHaveLength(0)
    expect(wrapper.findAll('a[data-to="/store/skills"] [data-icon="storage"]')).toHaveLength(1)
    expect(wrapper.findAll('a[data-to="/store/skills"] [data-icon="relation"]')).toHaveLength(0)
    expect(wrapper.findAll('a[data-to="/store/mcp"] [data-icon="computer"]')).toHaveLength(1)
    expect(wrapper.findAll('a[data-to="/store/mcp"] [data-icon="storage"]')).toHaveLength(0)
  })

  it('keeps auto-loading recent conversations until the list becomes scrollable', async () => {
    const calledLimits: number[] = []
    const recentConversationPages = [
      Array.from({ length: 13 }, (_item, index) => createRecentConversation(index)),
      Array.from({ length: 30 }, (_item, index) => createRecentConversation(index)),
      Array.from({ length: 35 }, (_item, index) => createRecentConversation(index)),
      Array.from({ length: 35 }, (_item, index) => createRecentConversation(index)),
    ]

    mocks.loadRecentConversations.mockImplementation(async (limit: number) => {
      calledLimits.push(limit)
      const nextList =
        limit <= 20
          ? recentConversationPages[0]
          : limit <= 40
            ? recentConversationPages[1]
            : limit <= 60
              ? recentConversationPages[2]
              : recentConversationPages[3]
      mocks.recentConversationsRef.value = nextList as any
    })

    const wrapper = mountSidebar()
    const list = wrapper.get('.recent-conversation-list')

    Object.defineProperty(list.element, 'scrollTop', {
      value: 0,
      writable: true,
      configurable: true,
    })
    Object.defineProperty(list.element, 'clientHeight', {
      value: 400,
      configurable: true,
    })
    Object.defineProperty(list.element, 'scrollHeight', {
      value: 400,
      configurable: true,
    })

    await flushPromises()
    await flushPromises()

    expect(calledLimits).toEqual([20, 40, 60, 80])
    expect(mocks.loadRecentConversations).toHaveBeenCalledTimes(4)
    expect(wrapper.text()).toContain('Conversation 35')
  })

  it('loads more recent conversations when the sidebar list reaches the bottom', async () => {
    mocks.allRecentConversations = Array.from({ length: 80 }, (_item, index) => ({
      id: `conversation-${index + 1}`,
      name: `Conversation ${index + 1}`,
      source_type: index % 2 === 0 ? 'assistant_agent' : 'app_debugger',
      app_id: index % 2 === 0 ? '' : `app-${index + 1}`,
      message_id: `message-${index + 1}`,
    }))
    mocks.loadRecentConversations.mockImplementation(async (limit: number) => {
      const nextList = mocks.allRecentConversations.slice(0, limit)
      mocks.recentConversationsRef.value = nextList
    })

    const wrapper = mountSidebar()
    const list = wrapper.get('.recent-conversation-list')
    Object.defineProperty(list.element, 'scrollTop', {
      value: 200,
      writable: true,
      configurable: true,
    })
    Object.defineProperty(list.element, 'clientHeight', {
      value: 200,
      configurable: true,
    })
    Object.defineProperty(list.element, 'scrollHeight', {
      value: 380,
      configurable: true,
    })

    await flushPromises()

    expect(mocks.loadRecentConversations).toHaveBeenCalledWith(20)

    await list.trigger('scroll')
    await flushPromises()

    expect(mocks.loadRecentConversations).toHaveBeenCalledWith(40)
    expect(wrapper.text()).toContain('Conversation 40')

    await list.trigger('scroll')
    await flushPromises()

    Object.defineProperty(list.element, 'scrollTop', {
      value: 120,
      writable: true,
      configurable: true,
    })
    await list.trigger('scroll')
    await flushPromises()

    Object.defineProperty(list.element, 'scrollTop', {
      value: 200,
      writable: true,
      configurable: true,
    })
    await list.trigger('scroll')
    await flushPromises()

    expect(mocks.loadRecentConversations).toHaveBeenCalledWith(60)
    expect(wrapper.text()).toContain('Conversation 60')
    expect(mocks.loadRecentConversations).toHaveBeenCalledTimes(3)

    await list.trigger('scroll')
    await flushPromises()

    expect(mocks.loadRecentConversations).toHaveBeenCalledTimes(3)
    expect(mocks.loadRecentConversations).not.toHaveBeenCalledWith(80)
  })
})
