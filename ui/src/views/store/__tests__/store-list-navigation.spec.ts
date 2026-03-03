import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import PublicAppsListView from '@/views/store/public-apps/ListView.vue'
import WorkflowsListView from '@/views/store/workflows/ListView.vue'

const mocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  getPublicApps: vi.fn(),
  getAppCategories: vi.fn(),
  forkPublicApp: vi.fn(),
  likeApp: vi.fn(),
  favoriteApp: vi.fn(),
  getPublicWorkflows: vi.fn(),
  forkPublicWorkflow: vi.fn(),
  likeWorkflow: vi.fn(),
  favoriteWorkflow: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mocks.routerPush,
  }),
}))

vi.mock('@/services/public-app', () => ({
  getPublicApps: mocks.getPublicApps,
  getAppCategories: mocks.getAppCategories,
  forkPublicApp: mocks.forkPublicApp,
  likeApp: mocks.likeApp,
  favoriteApp: mocks.favoriteApp,
}))

vi.mock('@/services/public-workflow', () => ({
  getPublicWorkflows: mocks.getPublicWorkflows,
  forkPublicWorkflow: mocks.forkPublicWorkflow,
  likeWorkflow: mocks.likeWorkflow,
  favoriteWorkflow: mocks.favoriteWorkflow,
}))

const slotStub = {
  template: '<div><slot /></div>',
}

const globalStubs = {
  'a-spin': slotStub,
  'a-avatar': slotStub,
  'a-input-search': {
    template: '<input />',
  },
  'a-tag': slotStub,
  'a-button': {
    template: '<button><slot /></button>',
  },
  'a-card': slotStub,
  'a-col': slotStub,
  'a-empty': slotStub,
  'a-row': slotStub,
  'a-pagination': slotStub,
  'icon-apps': slotStub,
  'icon-relation': slotStub,
  'icon-heart': slotStub,
  'icon-star': slotStub,
  'icon-branch': slotStub,
}

describe('store list navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mocks.getAppCategories.mockResolvedValue({
      data: {
        categories: [{ value: 'assistant', label: '助手' }],
      },
    })

    mocks.getPublicApps.mockResolvedValue({
      data: {
        list: [
          {
            id: 'app-1',
            name: '应用一',
            icon: '',
            description: '应用描述',
            category: 'assistant',
            view_count: 0,
            like_count: 1,
            fork_count: 2,
            favorite_count: 3,
            creator_name: 'tester',
            published_at: 1700000000,
            created_at: 1700000000,
            is_liked: false,
            is_favorited: false,
          },
        ],
        paginator: {
          total_record: 1,
        },
      },
    })

    mocks.getPublicWorkflows.mockResolvedValue({
      data: {
        list: [
          {
            id: 'workflow-1',
            name: '工作流一',
            icon: '',
            description: '工作流描述',
            category: 'assistant',
            view_count: 0,
            like_count: 1,
            fork_count: 2,
            favorite_count: 3,
            published_at: 1700000000,
            created_at: 1700000000,
            is_liked: false,
            is_favorited: false,
            account_name: 'tester',
          },
        ],
        paginator: {
          total_record: 1,
        },
      },
    })
  })

  it('navigates when clicking a public app card button', async () => {
    const wrapper = shallowMount(PublicAppsListView, {
      global: {
        stubs: globalStubs,
      },
    })
    await flushPromises()

    const previewButton = wrapper.find('button.w-full')
    expect(previewButton.exists()).toBe(true)
    expect(previewButton.attributes('type')).toBe('button')

    await previewButton.trigger('click')

    expect(mocks.routerPush).toHaveBeenCalledWith({
      name: 'store-public-apps-preview',
      params: { app_id: 'app-1' },
    })
  })

  it('navigates when clicking a workflow card button', async () => {
    const wrapper = shallowMount(WorkflowsListView, {
      global: {
        stubs: globalStubs,
      },
    })
    await flushPromises()

    const previewButton = wrapper.find('button.w-full')
    expect(previewButton.exists()).toBe(true)
    expect(previewButton.attributes('type')).toBe('button')

    await previewButton.trigger('click')

    expect(mocks.routerPush).toHaveBeenCalledWith({
      name: 'store-workflows-preview',
      params: { workflow_id: 'workflow-1' },
    })
  })
})
