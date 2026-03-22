import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ConversationSearchView from '../ConversationSearchView.vue'
import * as conversationSearchService from '@/services/conversation-search'
import * as conversationHook from '@/hooks/use-conversation'

// Mock services
vi.mock('@/services/conversation-search', () => ({
  searchConversations: vi.fn(),
  deleteConversation: vi.fn(),
}))

vi.mock('@/hooks/use-conversation', () => ({
  useGetRecentConversations: vi.fn(),
  useDeleteConversation: vi.fn(),
}))

vi.mock('@/components/AiDynamicBackground.vue', () => ({
  default: { name: 'AiDynamicBackground', template: '<div></div>' },
}))

vi.mock('@/views/layouts/components/UpdateConversationNameModal.vue', () => ({
  default: { name: 'UpdateConversationNameModal', template: '<div></div>' },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

const createWrapper = (stubs = {}) => {
  return mount(ConversationSearchView, {
    global: {
      stubs: {
        'a-dropdown': true,
        'a-button': true,
        'a-doption': true,
        'icon-message': true,
        'icon-apps': true,
        'icon-more': true,
        'icon-edit': true,
        'icon-delete': true,
        ...stubs,
      },
      mocks: {
        $router: {
          push: vi.fn(),
        },
      },
    },
  })
}

describe('ConversationSearchView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders search input', () => {
    vi.mocked(conversationHook.useGetRecentConversations).mockReturnValue({
      loading: false,
      conversations: [],
      loadRecentConversations: vi.fn(),
    } as any)

    vi.mocked(conversationHook.useDeleteConversation).mockReturnValue({
      handleDeleteConversation: vi.fn(),
    } as any)

    vi.mocked(conversationSearchService.searchConversations).mockResolvedValue([])

    const wrapper = createWrapper()

    const searchInput = wrapper.find('input[type="text"]')
    expect(searchInput.exists()).toBe(true)
    expect(searchInput.attributes('placeholder')).toContain('搜索对话')
  })

  it('displays recent conversations as cards when search is empty', async () => {
    const mockRecentConversations = [
      {
        id: 'conv-1',
        name: '测试对话 1',
        app_name: '应用 A',
        human_message: '你好，这是第一条消息',
        ai_message: '你好！很高兴认识你',
        source_type: 'assistant_agent' as const,
        app_id: 'app-1',
        message_id: 'msg-1',
        is_active: true,
        latest_message_at: Math.floor(Date.now() / 1000) - 3600,
        created_at: Math.floor(Date.now() / 1000) - 7200,
      },
    ]

    vi.mocked(conversationHook.useGetRecentConversations).mockReturnValue({
      loading: false,
      conversations: mockRecentConversations,
      loadRecentConversations: vi.fn(),
    } as any)

    vi.mocked(conversationHook.useDeleteConversation).mockReturnValue({
      handleDeleteConversation: vi.fn(),
    } as any)

    vi.mocked(conversationSearchService.searchConversations).mockResolvedValue([])

    const wrapper = createWrapper()

    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))

    const cardContent = wrapper.html()
    expect(cardContent).toContain('测试对话 1')
    expect(cardContent).toContain('应用 A')
    expect(cardContent).toContain('你好，这是第一条消息')
    expect(cardContent).toContain('你好！很高兴认识你')
  })

  it('displays search results as cards', async () => {
    const mockSearchResults = [
      {
        id: 'conv-1',
        name: '搜索结果对话',
        app_name: '应用',
        human_message: '搜索匹配的用户消息',
        ai_message: '搜索匹配的AI回复',
        source_type: 'assistant_agent' as const,
        app_id: 'app-1',
        message_id: 'msg-1',
        is_active: true,
        latest_message_at: Math.floor(Date.now() / 1000),
        created_at: Math.floor(Date.now() / 1000),
      },
    ]

    vi.mocked(conversationHook.useGetRecentConversations).mockReturnValue({
      loading: false,
      conversations: [],
      loadRecentConversations: vi.fn(),
    } as any)

    vi.mocked(conversationHook.useDeleteConversation).mockReturnValue({
      handleDeleteConversation: vi.fn(),
    } as any)

    vi.mocked(conversationSearchService.searchConversations).mockResolvedValue(mockSearchResults)

    const wrapper = createWrapper()

    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))

    const cardContent = wrapper.html()
    expect(cardContent).toContain('搜索结果对话')
    expect(cardContent).toContain('应用')
    expect(cardContent).toContain('搜索匹配的用户消息')
    expect(cardContent).toContain('搜索匹配的AI回复')
  })

  it('displays app_name badge in card', async () => {
    const mockRecentConversations = [
      {
        id: 'conv-1',
        name: '测试对话',
        app_name: '我的应用',
        human_message: '消息',
        ai_message: '回复',
        source_type: 'assistant_agent' as const,
        app_id: 'app-1',
        message_id: 'msg-1',
        is_active: true,
        latest_message_at: Math.floor(Date.now() / 1000),
        created_at: Math.floor(Date.now() / 1000),
      },
    ]

    vi.mocked(conversationHook.useGetRecentConversations).mockReturnValue({
      loading: false,
      conversations: mockRecentConversations,
      loadRecentConversations: vi.fn(),
    } as any)

    vi.mocked(conversationHook.useDeleteConversation).mockReturnValue({
      handleDeleteConversation: vi.fn(),
    } as any)

    vi.mocked(conversationSearchService.searchConversations).mockResolvedValue([])

    const wrapper = createWrapper()

    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))

    const cardContent = wrapper.html()
    expect(cardContent).toContain('我的应用')
    expect(cardContent).toContain('bg-blue-100')
  })

  it('displays formatted date in card', async () => {
    const mockRecentConversations = [
      {
        id: 'conv-1',
        name: '测试对话',
        app_name: '应用',
        human_message: '消息',
        ai_message: '回复',
        source_type: 'assistant_agent' as const,
        app_id: 'app-1',
        message_id: 'msg-1',
        is_active: true,
        latest_message_at: 1710835200, // 2024-03-19 00:00:00 UTC
        created_at: 1710835200,
      },
    ]

    vi.mocked(conversationHook.useGetRecentConversations).mockReturnValue({
      loading: false,
      conversations: mockRecentConversations,
      loadRecentConversations: vi.fn(),
    } as any)

    vi.mocked(conversationHook.useDeleteConversation).mockReturnValue({
      handleDeleteConversation: vi.fn(),
    } as any)

    vi.mocked(conversationSearchService.searchConversations).mockResolvedValue([])

    const wrapper = createWrapper()

    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))

    const cardContent = wrapper.html()
    // 验证日期格式化
    expect(cardContent).toMatch(/\d{4}年\d{1,2}月\d{1,2}日 \d{2}:\d{2}/)
  })

  it('shows menu with rename and delete options on hover', async () => {
    const mockRecentConversations = [
      {
        id: 'conv-1',
        name: '测试对话',
        app_name: '应用',
        human_message: '消息',
        ai_message: '回复',
        source_type: 'assistant_agent' as const,
        app_id: 'app-1',
        message_id: 'msg-1',
        is_active: true,
        latest_message_at: Math.floor(Date.now() / 1000),
        created_at: Math.floor(Date.now() / 1000),
      },
    ]

    vi.mocked(conversationHook.useGetRecentConversations).mockReturnValue({
      loading: false,
      conversations: mockRecentConversations,
      loadRecentConversations: vi.fn(),
    } as any)

    vi.mocked(conversationHook.useDeleteConversation).mockReturnValue({
      handleDeleteConversation: vi.fn(),
    } as any)

    vi.mocked(conversationSearchService.searchConversations).mockResolvedValue([])

    const wrapper = createWrapper()

    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))

    // 验证菜单项在 DOM 中存在
    const cardContent = wrapper.html()
    expect(cardContent).toContain('重命名')
    expect(cardContent).toContain('删除会话')
  })

  it('truncates long messages', () => {
    vi.mocked(conversationHook.useGetRecentConversations).mockReturnValue({
      loading: false,
      conversations: [],
      loadRecentConversations: vi.fn(),
    } as any)

    vi.mocked(conversationHook.useDeleteConversation).mockReturnValue({
      handleDeleteConversation: vi.fn(),
    } as any)

    vi.mocked(conversationSearchService.searchConversations).mockResolvedValue([])

    const wrapper = createWrapper()

    const longText = 'a'.repeat(150)
    const truncated = wrapper.vm.truncateText(longText, 80)
    expect(truncated.length).toBeLessThanOrEqual(83) // 80 + '...'
    expect(truncated).toContain('...')
  })

  it('formats date correctly', () => {
    vi.mocked(conversationHook.useGetRecentConversations).mockReturnValue({
      loading: false,
      conversations: [],
      loadRecentConversations: vi.fn(),
    } as any)

    vi.mocked(conversationHook.useDeleteConversation).mockReturnValue({
      handleDeleteConversation: vi.fn(),
    } as any)

    vi.mocked(conversationSearchService.searchConversations).mockResolvedValue([])

    const wrapper = createWrapper()

    const timestamp = 1710835200 // 2024-03-19 00:00:00 UTC
    const formatted = wrapper.vm.formatDate(timestamp)
    expect(formatted).toMatch(/\d{4}年\d{1,2}月\d{1,2}日 \d{2}:\d{2}/)
  })
})
