import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import HistoryView from '@/views/conversation/HistoryView.vue'
import { useGetRecentConversations, useDeleteConversation } from '@/hooks/use-conversation'
import { useRouter } from 'vue-router'

// Mock hooks
vi.mock('@/hooks/use-conversation', () => ({
  useGetRecentConversations: vi.fn(),
  useDeleteConversation: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: vi.fn(),
}))

describe('HistoryView - 对话历史页面', () => {
  let mockConversations: any[]

  beforeEach(() => {
    mockConversations = [
      {
        id: '1',
        name: '测试对话1',
        human_message: '你好',
        ai_message: '你好！',
        created_at: Math.floor(Date.now() / 1000),
        source_type: 'assistant_agent',
      },
      {
        id: '2',
        name: '测试对话2',
        human_message: '分析',
        ai_message: '分析结果',
        created_at: Math.floor(Date.now() / 1000) - 86400,
        source_type: 'app_debugger',
        app_id: 'app-123',
      },
    ]

    vi.mocked(useGetRecentConversations).mockReturnValue({
      loading: ref(false),
      conversations: ref(mockConversations),
      loadRecentConversations: vi.fn(),
    } as any)

    vi.mocked(useDeleteConversation).mockReturnValue({
      handleDeleteConversation: vi.fn(),
    } as any)

    vi.mocked(useRouter).mockReturnValue({
      push: vi.fn(),
    } as any)
  })

  it('应该显示对话列表', () => {
    const wrapper = mount(HistoryView, {
      global: {
        stubs: {
          UpdateConversationNameModal: true,
          'a-input-search': true,
          'a-skeleton': true,
          'a-dropdown': true,
          'a-button': true,
          'a-doption': true,
        },
      },
    })

    expect(wrapper.text()).toContain('测试对话1')
    expect(wrapper.text()).toContain('测试对话2')
  })

  it('应该支持搜索对话', async () => {
    const wrapper = mount(HistoryView, {
      global: {
        stubs: {
          UpdateConversationNameModal: true,
          'a-input-search': true,
          'a-skeleton': true,
          'a-dropdown': true,
          'a-button': true,
          'a-doption': true,
        },
      },
    })

    // 模拟搜索
    const vm = wrapper.vm as any
    vm.searchQuery = '测试对话1'

    await wrapper.vm.$nextTick()

    expect(vm.filteredConversations).toHaveLength(1)
    expect(vm.filteredConversations[0].name).toBe('测试对话1')
  })

  it('应该能打开编辑名称模态窗', async () => {
    const wrapper = mount(HistoryView, {
      global: {
        stubs: {
          UpdateConversationNameModal: true,
          'a-input-search': true,
          'a-skeleton': true,
          'a-dropdown': true,
          'a-button': true,
          'a-doption': true,
        },
      },
    })

    const vm = wrapper.vm as any
    const conversation = mockConversations[0]

    vm.openUpdateNameModal(conversation)

    expect(vm.updateConversationNameVisible).toBe(true)
    expect(vm.updateConversationNameId).toBe('1')
    expect(vm.updateConversationName).toBe('测试对话1')
  })

  it('应该能删除单个对话', async () => {
    const mockHandleDelete = vi.fn()
    vi.mocked(useDeleteConversation).mockReturnValue({
      handleDeleteConversation: mockHandleDelete,
    } as any)

    const wrapper = mount(HistoryView, {
      global: {
        stubs: {
          UpdateConversationNameModal: true,
          'a-input-search': true,
          'a-skeleton': true,
          'a-dropdown': true,
          'a-button': true,
          'a-doption': true,
        },
      },
    })

    const vm = wrapper.vm as any
    const conversation = mockConversations[0]

    vm.deleteConversation(conversation)

    expect(mockHandleDelete).toHaveBeenCalledWith('1', expect.any(Function))
  })

  it('编辑名称成功后应该更新对话列表', async () => {
    const wrapper = mount(HistoryView, {
      global: {
        stubs: {
          UpdateConversationNameModal: true,
          'a-input-search': true,
          'a-skeleton': true,
          'a-dropdown': true,
          'a-button': true,
          'a-doption': true,
        },
      },
    })

    const vm = wrapper.vm as any
    vm.updateConversationNameSuccess('1', '新名称')

    expect(vm.allConversations[0].name).toBe('新名称')
  })

  it('应该正确格式化日期', () => {
    const wrapper = mount(HistoryView, {
      global: {
        stubs: {
          UpdateConversationNameModal: true,
          'a-input-search': true,
          'a-skeleton': true,
          'a-dropdown': true,
          'a-button': true,
          'a-doption': true,
        },
      },
    })

    const vm = wrapper.vm as any
    const today = Math.floor(Date.now() / 1000)
    const yesterday = today - 86400

    expect(vm.formatDate(today)).toBe('今天')
    expect(vm.formatDate(yesterday)).toBe('昨天')
  })

  it('应该截断过长标题', () => {
    const wrapper = mount(HistoryView, {
      global: {
        stubs: {
          UpdateConversationNameModal: true,
          'a-input-search': true,
          'a-skeleton': true,
          'a-dropdown': true,
          'a-button': true,
          'a-doption': true,
        },
      },
    })

    const vm = wrapper.vm as any
    expect(vm.truncateText('12345678901234567890')).toBe('12345678901234567890')
    expect(vm.truncateText('123456789012345678901')).toBe('12345678901234567890...')
  })

  it('应该能跳转到对话', async () => {
    const mockPush = vi.fn()
    vi.mocked(useRouter).mockReturnValue({
      push: mockPush,
    } as any)

    const wrapper = mount(HistoryView, {
      global: {
        stubs: {
          UpdateConversationNameModal: true,
          'a-input-search': true,
          'a-skeleton': true,
          'a-dropdown': true,
          'a-button': true,
          'a-doption': true,
        },
      },
    })

    const vm = wrapper.vm as any
    const conversation = mockConversations[0]

    vm.goToConversation(conversation)

    expect(mockPush).toHaveBeenCalledWith({
      path: '/home',
      query: { conversation_id: '1' },
    })
  })
})
