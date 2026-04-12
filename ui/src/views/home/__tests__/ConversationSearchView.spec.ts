import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ConversationSearchView from '../ConversationSearchView.vue'
import * as conversationHooks from '@/hooks/use-conversation'
import * as conversationSearchService from '@/services/conversation-search'

const routerPush = vi.fn()

vi.mock('@/services/conversation-search', () => ({
 searchConversations: vi.fn(),
 deleteConversation: vi.fn(),
}))

vi.mock('@/hooks/use-conversation', () => ({
 useGetRecentConversations: vi.fn(),
 useDeleteConversation: vi.fn(),
}))

vi.mock('@/components/AiDynamicBackground.vue', () => ({
 default: { name: 'AiDynamicBackground', template: '<div />' },
}))

vi.mock('@/views/layouts/components/UpdateConversationNameModal.vue', () => ({
 default: { name: 'UpdateConversationNameModal', template: '<div />' },
}))

vi.mock('vue-router', () => ({
 useRouter: () => ({
 push: routerPush,
 }),
}))

const dropdownStub = {
 props: ['popupVisible'],
 template: '<div><slot /> <div v-if="popupVisible"><slot name="content" /></div></div>',
}

const buttonStub = {
 emits: ['click'],
 template: '<button type="button" @click.stop="$emit(\'click\', $event)"><slot /><slot name="icon" /></button>',
}

const optionStub = {
 emits: ['click'],
 template: '<button type="button" @click.stop="$emit(\'click\', $event)"><slot /><slot name="icon" /></button>',
}

const buildConversation = (overrides: Record<string, unknown> = {}) => ({
 id: 'conversation-1',
 name: '最近对话',
 app_name: '助手应用',
 agent_name: '',
 human_message: '你好，帮我写个测试',
 ai_message: '可以，先从核心路径开始。',
 matched_fields: [],
 source_type: 'assistant_agent',
 app_id: 'app-1',
 message_id: 'message-1',
 is_active: true,
 latest_message_at:1710835200,
 created_at:1710835200,
 ...overrides,
})

const mountView = () => {
 return mount(ConversationSearchView, {
 global: {
 stubs: {
 'a-dropdown': dropdownStub,
 'a-button': buttonStub,
 'a-doption': optionStub,
 'icon-more': true,
 'icon-edit': true,
 'icon-delete': true,
 },
 },
 })
}

describe('ConversationSearchView', () => {
 beforeEach(() => {
 vi.clearAllMocks()
 vi.mocked(conversationHooks.useGetRecentConversations).mockReturnValue({
 loading: ref(false),
 conversations: ref([]),
 loadRecentConversations: vi.fn(),
 } as never)
 vi.mocked(conversationHooks.useDeleteConversation).mockReturnValue({
 handleDeleteConversation: vi.fn(),
 } as never)
 vi.mocked(conversationSearchService.searchConversations).mockResolvedValue({
 data: [],
 } as never)
 })

 it('renders recent conversations when the search box is empty', async () => {
 const loadRecentConversations = vi.fn()
 vi.mocked(conversationHooks.useGetRecentConversations).mockReturnValue({
 loading: ref(false),
 conversations: ref([buildConversation()]),
 loadRecentConversations,
 } as never)

 const wrapper = mountView()
 await flushPromises()

 expect(loadRecentConversations).toHaveBeenCalledWith(20)
 expect(wrapper.text()).toContain('最近对话')
 expect(wrapper.text()).toContain('助手应用')
 expect(wrapper.text()).toContain('你好，帮我写个测试')
 expect(wrapper.text()).toContain('可以，先从核心路径开始。')
 })

 it('searches and renders matched conversations from the API', async () => {
 vi.mocked(conversationSearchService.searchConversations).mockResolvedValue({
 data: [
 buildConversation({
 id: 'conversation-2',
 name: 'Python 编程教程',
 app_name: '搜索结果应用',
 human_message: '如何学习 Python',
 ai_message: 'Python 入门建议先写小项目',
 matched_fields: ['name', 'human_message', 'ai_message'],
 }),
 ],
 } as never)

 const wrapper = mountView()
 await wrapper.get('[data-testid="conversation-search-input"]').setValue('Python')
 await flushPromises()

 expect(conversationSearchService.searchConversations).toHaveBeenLastCalledWith('Python',100)
 expect(wrapper.text()).toContain('Python 编程教程')
 expect(wrapper.text()).toContain('搜索结果应用')
 const cardClasses = wrapper.get('[data-testid="conversation-card"]').classes()
 expect(cardClasses).toContain('min-h-[108px]')
 expect(cardClasses).not.toContain('h-[144px]')
 })

 it('highlights matched keywords in title and message preview', async () => {
 vi.mocked(conversationSearchService.searchConversations).mockResolvedValue({
 data: [
 buildConversation({
 id: 'conversation-highlight',
 name: 'Python 编程教程',
 human_message: '如何学习 Python',
 ai_message: '建议先掌握 Python 基础语法',
 matched_fields: ['name', 'human_message', 'ai_message'],
 }),
 ],
 } as never)

 const wrapper = mountView()
 await wrapper.get('[data-testid="conversation-search-input"]').setValue('Python')
 await flushPromises()

 const highlightedNodes = wrapper.findAll('.gradient-highlight')
 expect(highlightedNodes.length).toBeGreaterThan(0)
 expect(wrapper.html()).toContain('<span class="gradient-highlight">Python</span>')
 })

 it('still highlights keyword when match is in second line of message', async () => {
  vi.mocked(conversationSearchService.searchConversations).mockResolvedValue({
 data: [
 buildConversation({
 id: 'conversation-multiline',
 name: '多行命中测试',
 human_message: '第一行没有关键词\n第二行包含 **Python** 关键词',
 ai_message: '回答第一行\n回答第二行也有 `Python`',
 matched_fields: ['human_message', 'ai_message'],
 }),
 ],
 } as never)

 const wrapper = mountView()
 await wrapper.get('[data-testid="conversation-search-input"]').setValue('Python')
 await flushPromises()

 expect(wrapper.html()).toContain('<span class="gradient-highlight">Python</span>')
 expect(wrapper.html()).toContain('<strong>')
 expect(wrapper.html()).toContain('<code>')
 })

 it('explains title-only matches instead of showing unrelated message preview', async () => {
 vi.mocked(conversationSearchService.searchConversations).mockResolvedValue({
 data: [
 buildConversation({
 id: 'conversation-title-only',
 name: 'Python 编程教程',
 human_message: '这个问题没有命中词',
 ai_message: '这个回答也没有命中词',
 matched_fields: ['name'],
 }),
 ],
 } as never)

 const wrapper = mountView()
 await wrapper.get('[data-testid="conversation-search-input"]').setValue('Python')
 await flushPromises()

 expect(wrapper.text()).toContain('关键词命中标题')
 expect(wrapper.text()).not.toContain('这个问题没有命中词')
 expect(wrapper.text()).not.toContain('这个回答也没有命中词')
 })

  it('uses OpenAgent as the assistant match label', async () => {
 vi.mocked(conversationSearchService.searchConversations).mockResolvedValue({
 data: [
 buildConversation({
 id: 'conversation-agent-name',
 name: '智能体名称命中',
 agent_name: 'OpenAgent',
 human_message: '',
 ai_message: '',
 matched_fields: ['agent_name'],
 }),
 ],
 } as never)

 const wrapper = mountView()
 await wrapper.get('[data-testid="conversation-search-input"]').setValue('OpenAgent')
 await flushPromises()

 expect(wrapper.text()).toContain('关键词命中OpenAgent')
 expect(wrapper.text()).toContain('OpenAgent')
  })

  it('truncates long conversation titles with ellipsis', async () => {
    vi.mocked(conversationHooks.useGetRecentConversations).mockReturnValue({
      loading: ref(false),
      conversations: ref([buildConversation({ name: '1234567890123456789012345' })]),
      loadRecentConversations: vi.fn(),
    } as never)

    const wrapper = mountView()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.truncateText('12345678901234567890')).toBe('12345678901234567890')
    expect(vm.truncateText('123456789012345678901')).toBe('12345678901234567890...')
  })

  it('shows menu items only after clicking the more icon', async () => {
 vi.mocked(conversationSearchService.searchConversations).mockResolvedValue({
 data: [
 buildConversation({
 id: 'conversation-menu',
 name: '菜单交互测试',
 }),
 ],
 } as never)

 const wrapper = mountView()
 await wrapper.get('[data-testid="conversation-search-input"]').setValue('菜单')
 await flushPromises()

 const card = wrapper.get('[data-testid="conversation-card"]')
 await card.trigger('mouseenter')

 expect(wrapper.text()).not.toContain('重命名')
 expect(wrapper.text()).not.toContain('删除会话')

 await card.get('button').trigger('click')
 await flushPromises()

 expect(wrapper.text()).toContain('重命名')
 expect(wrapper.text()).toContain('删除会话')
 })

 it('navigates debugger conversations to the target app workspace', async () => {
 vi.mocked(conversationSearchService.searchConversations).mockResolvedValue({
 data: [
 buildConversation({
 id: 'debug-1',
 source_type: 'app_debugger',
 app_id: 'app-42',
 message_id: 'message-42',
 name: '调试会话',
 }),
 ],
 } as never)

 const wrapper = mountView()
 await wrapper.get('[data-testid="conversation-search-input"]').setValue('调试')
 await flushPromises()
 await wrapper.get('[data-testid="conversation-card"]').trigger('click')

 expect(routerPush).toHaveBeenCalledWith({
 path: '/space/apps/app-42',
 query: {
 conversation_id: 'debug-1',
 message_id: 'message-42',
 },
 })
 })

 it('forwards wheel events from page blank area to conversation scroller', async () => {
 vi.mocked(conversationHooks.useGetRecentConversations).mockReturnValue({
 loading: ref(false),
 conversations: ref([
 buildConversation({ id: 'conversation-1' }),
 buildConversation({ id: 'conversation-2', name: '第二个会话' }),
 ]),
 loadRecentConversations: vi.fn(),
 } as never)

 const wrapper = mountView()
 await flushPromises()

 const page = wrapper.get('[data-testid="conversation-search-page"]')
 const scroller = wrapper.get('[data-testid="conversation-search-scroll-area"]').element as HTMLElement

 Object.defineProperty(scroller, 'scrollHeight', { configurable: true, value:1200 })
 Object.defineProperty(scroller, 'clientHeight', { configurable: true, value:400 })
 Object.defineProperty(scroller, 'scrollTop', { configurable: true, writable: true, value:100 })

 await page.trigger('wheel', { deltaX:0, deltaY:120 })

 expect(scroller.scrollTop).toBe(220)
 })
})
