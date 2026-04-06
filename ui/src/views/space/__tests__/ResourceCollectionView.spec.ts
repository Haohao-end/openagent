import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ResourceCollectionView from '@/views/space/components/ResourceCollectionView.vue'

const mocks = vi.hoisted(() => ({
  route: { query: {} as Record<string, string> },
  routerPush: vi.fn(),
  getLikes: vi.fn(),
  getFavorites: vi.fn(),
  likeApp: vi.fn(),
  likeWorkflow: vi.fn(),
  favoriteApp: vi.fn(),
  favoriteWorkflow: vi.fn(),
  forkPublicApp: vi.fn(),
  forkPublicWorkflow: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({
    push: mocks.routerPush,
  }),
}))

vi.mock('@/services/like', () => ({
  getLikes: mocks.getLikes,
}))

vi.mock('@/services/favorite', () => ({
  getFavorites: mocks.getFavorites,
}))

vi.mock('@/services/public-app', () => ({
  likeApp: mocks.likeApp,
  favoriteApp: mocks.favoriteApp,
  forkPublicApp: mocks.forkPublicApp,
}))

vi.mock('@/services/public-workflow', () => ({
  likeWorkflow: mocks.likeWorkflow,
  favoriteWorkflow: mocks.favoriteWorkflow,
  forkPublicWorkflow: mocks.forkPublicWorkflow,
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: mocks.messageSuccess,
    error: mocks.messageError,
    warning: mocks.messageWarning,
  },
}))

const slotStub = {
  template: '<div><slot /></div>',
}

const globalStubs = {
  'a-spin': slotStub,
  'a-card': slotStub,
  'a-avatar': slotStub,
  'a-tag': slotStub,
  'a-empty': slotStub,
  'a-tooltip': slotStub,
  'icon-branch': slotStub,
  'icon-eye': slotStub,
}

const makeAppItem = (overrides: Record<string, unknown> = {}) => ({
  id: 'app-1',
  resource_type: 'app',
  name: '默认应用',
  icon: '',
  description: '应用描述',
  category: 'assistant',
  view_count: 1,
  like_count: 9011,
  fork_count: 9033,
  favorite_count: 9022,
  creator_name: 'Alice',
  creator_avatar: '',
  published_at: 1700000000,
  created_at: 1700000000,
  action_at: 1700000001,
  is_liked: true,
  is_favorited: true,
  is_forked: false,
  ...overrides,
})

const makeWorkflowItem = (overrides: Record<string, unknown> = {}) => ({
  id: 'workflow-1',
  resource_type: 'workflow',
  name: '默认工作流',
  icon: '',
  description: '工作流描述',
  category: 'assistant',
  view_count: 2,
  like_count: 9112,
  fork_count: 9134,
  favorite_count: 9123,
  creator_name: 'Bob',
  creator_avatar: '',
  published_at: 1700000002,
  created_at: 1700000002,
  action_at: 1700000003,
  is_liked: true,
  is_favorited: true,
  is_forked: false,
  ...overrides,
})

const renderView = async (mode: 'likes' | 'favorites') => {
  const wrapper = mount(ResourceCollectionView, {
    props: { mode },
    global: {
      stubs: globalStubs,
    },
  })
  await flushPromises()
  return wrapper
}

const findButtonContainingText = (wrapper: ReturnType<typeof mount>, text: string) => {
  return wrapper.findAll('button').find((button) => button.text().includes(text))
}

describe('ResourceCollectionView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.query = {}

    mocks.getLikes.mockImplementation(({ resource_type }: { resource_type: string }) =>
      Promise.resolve({
        data: resource_type === 'workflow'
          ? [makeWorkflowItem({ name: '代码流 Beta' })]
          : [makeAppItem({ name: '天气助手 Alpha' })],
      }),
    )

    mocks.getFavorites.mockImplementation(({ resource_type }: { resource_type: string }) =>
      Promise.resolve({
        data: resource_type === 'workflow'
          ? [makeWorkflowItem({ name: '数据流 Delta' })]
          : [makeAppItem({ name: '翻译应用 Gamma' })],
      }),
    )

    mocks.likeApp.mockResolvedValue({
      data: { is_liked: false, like_count: 9010 },
    })
    mocks.likeWorkflow.mockResolvedValue({
      data: { is_liked: false, like_count: 9010 },
    })
    mocks.favoriteApp.mockResolvedValue({
      data: { is_favorited: false, favorite_count: 9021 },
    })
    mocks.favoriteWorkflow.mockResolvedValue({
      data: { is_favorited: false, favorite_count: 9021 },
    })
  })

  it('loads liked apps by default and can switch to liked workflows', async () => {
    const wrapper = await renderView('likes')

    expect(mocks.getLikes).toHaveBeenCalledWith({
      search_word: '',
      resource_type: 'app',
    })
    expect(wrapper.text()).toContain('天气助手 Alpha')

    const workflowSwitch = findButtonContainingText(wrapper, '工作流')
    expect(workflowSwitch).toBeTruthy()

    await workflowSwitch!.trigger('click')
    await flushPromises()

    expect(mocks.getLikes).toHaveBeenLastCalledWith({
      search_word: '',
      resource_type: 'workflow',
    })
    expect(wrapper.text()).toContain('代码流 Beta')
  })

  it('loads favorited apps by default and can switch to favorited workflows', async () => {
    const wrapper = await renderView('favorites')

    expect(mocks.getFavorites).toHaveBeenCalledWith({
      search_word: '',
      resource_type: 'app',
    })
    expect(wrapper.text()).toContain('翻译应用 Gamma')

    const workflowSwitch = findButtonContainingText(wrapper, '工作流')
    expect(workflowSwitch).toBeTruthy()

    await workflowSwitch!.trigger('click')
    await flushPromises()

    expect(mocks.getFavorites).toHaveBeenLastCalledWith({
      search_word: '',
      resource_type: 'workflow',
    })
    expect(wrapper.text()).toContain('数据流 Delta')
  })

  it('removes an item from likes after cancelling like', async () => {
    const wrapper = await renderView('likes')
    expect(wrapper.text()).toContain('天气助手 Alpha')

    const likeButton = findButtonContainingText(wrapper, '9011')
    expect(likeButton).toBeTruthy()

    await likeButton!.trigger('click')
    await flushPromises()

    expect(mocks.likeApp).toHaveBeenCalledWith('app-1')
    expect(wrapper.text()).not.toContain('天气助手 Alpha')
  })

  it('removes an item from favorites after cancelling favorite', async () => {
    const wrapper = await renderView('favorites')
    expect(wrapper.text()).toContain('翻译应用 Gamma')

    const favoriteButton = findButtonContainingText(wrapper, '9022')
    expect(favoriteButton).toBeTruthy()

    await favoriteButton!.trigger('click')
    await flushPromises()

    expect(mocks.favoriteApp).toHaveBeenCalledWith('app-1')
    expect(wrapper.text()).not.toContain('翻译应用 Gamma')
  })
})
