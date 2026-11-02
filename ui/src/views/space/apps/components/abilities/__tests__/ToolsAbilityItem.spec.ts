import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick, ref } from 'vue'

import ToolsAbilityItem from '../ToolsAbilityItem.vue'

const mocks = vi.hoisted(() => ({
  updateDraftAppConfig: vi.fn().mockResolvedValue({}),
  loadApiToolProviders: vi.fn().mockResolvedValue(undefined),
  loadBuiltinTools: vi.fn().mockResolvedValue(undefined),
  loadApiTool: vi.fn().mockResolvedValue(undefined),
  loadBuiltinTool: vi.fn().mockResolvedValue(undefined),
  loadCategories: vi.fn().mockResolvedValue(undefined),
  builtinTools: [] as Array<Record<string, unknown>>,
  builtinTool: null as any,
}))

vi.mock('@/hooks/use-app', () => ({
  useUpdateDraftAppConfig: () => ({
    loading: ref(false),
    handleUpdateDraftAppConfig: mocks.updateDraftAppConfig,
  }),
}))

vi.mock('@/hooks/use-tool', () => ({
  useGetApiTool: () => ({
    loading: ref(false),
    api_tool: ref({
      provider: {
        id: '',
        icon: '',
        name: '',
        label: '',
        description: '',
      },
      name: '',
      description: '',
      inputs: [],
      params: [],
    }),
    loadApiTool: mocks.loadApiTool,
  }),
  useGetApiToolProvidersWithPage: () => ({
    loading: ref(false),
    paginator: ref({
      total_page: 0,
      total_record: 0,
      current_page: 0,
      page_size: 50,
    }),
    api_tool_providers: ref([]),
    loadApiToolProviders: mocks.loadApiToolProviders,
  }),
}))

vi.mock('@/hooks/use-builtin-tool', () => ({
  useGetBuiltinTool: () => ({
    loading: ref(false),
    builtin_tool: ref(mocks.builtinTool || {
      provider: { name: '', label: '', description: '' },
      name: '', label: '', description: '', inputs: [], params: [],
    }),
    loadBuiltinTool: mocks.loadBuiltinTool,
  }),
  useGetBuiltinTools: () => ({
    builtin_tools: ref(mocks.builtinTools),
    loadBuiltinTools: mocks.loadBuiltinTools,
  }),
  useGetCategories: () => ({
    categories: ref([]),
    loadCategories: mocks.loadCategories,
  }),
}))

vi.mock('@/utils/store-display', () => ({
  getStoreCategoryDisplayName: (category: string) => category,
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    warning: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => {
  const translations: Record<string, string> = {
    'appStudio.abilities.tools.title': '扩展插件',
    'appStudio.abilities.tools.addTitle': '关联插件',
    'appStudio.abilities.tools.addDescription': '从插件广场或自定义插件中选择可关联的插件。',
    'appStudio.abilities.tools.customPlugin': '自定义插件',
    'appStudio.abilities.tools.builtinPlugin': '内置插件',
    'appStudio.abilities.tools.createCustomPlugin': '创建自定义插件',
    'appStudio.abilities.tools.all': '全部',
    'appStudio.abilities.tools.add': '添加',
    'appStudio.abilities.tools.remove': '移除',
    'common.actions.cancel': '取消',
    'common.actions.save': '保存',
  }

  return {
    useI18n: () => ({
      t: (key: string) => translations[key] || key,
      locale: { value: 'zh-CN' },
    }),
  }
})

const buttonStub = defineComponent({
  inheritAttrs: false,
  props: {
    loading: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
  },
  emits: ['click'],
  template: `
    <button v-bind="$attrs" :disabled="loading || disabled" @click="$emit('click', $event)">
      <slot />
      <slot name="icon" />
    </button>
  `,
})

const modalStub = defineComponent({
  inheritAttrs: false,
  props: {
    visible: { type: Boolean, default: false },
  },
  template: `
    <div v-if="visible" data-testid="tools-modal" v-bind="$attrs">
      <slot />
    </div>
  `,
})

const collapseItemStub = defineComponent({
  props: {
    header: {
      type: String,
      default: '',
    },
  },
  template: `
    <section>
      <header class="collapse-header">
        <slot name="header">{{ header }}</slot>
      </header>
      <div class="collapse-extra">
        <slot name="extra" />
      </div>
      <div class="collapse-content">
        <slot />
      </div>
    </section>
  `,
})

const radioGroupStub = defineComponent({ props: ['modelValue'], emits: ['update:modelValue'], template: '<div />' })
const slotStub = { template: '<div><slot /></div>' }

const mountToolsAbilityItem = () =>
  mount(ToolsAbilityItem, {
    props: {
      app_id: 'app-1',
      tools: [],
    },
    global: {
      stubs: {
        'a-collapse-item': collapseItemStub,
        'a-button': buttonStub,
        'a-modal': modalStub,
        'a-avatar': true,
        'a-tooltip': true,
        'a-form': slotStub,
        'a-form-item': slotStub,
        'a-input': true,
        'a-input-number': true,
        'a-select': true,
        'a-radio-group': radioGroupStub,
        'a-radio': true,
        'a-row': true,
        'a-col': true,
        'a-spin': true,
        'a-empty': true,
        'a-space': slotStub,
        'a-tag': true,
        'a-input-search': true,
        'a-divider': true,
        'router-link': true,
        'icon-plus': true,
        'icon-settings': true,
        'icon-delete': true,
        'icon-close': true,
        'icon-code': true,
        'icon-translate': true,
        'icon-apps': true,
        'icon-oblique-line': true,
        'icon-info-circle': true,
        'icon-question-circle': true,
      },
    },
  })

describe('ToolsAbilityItem', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('closes the marketplace modal when the top-right close button is clicked', async () => {
    const wrapper = mountToolsAbilityItem()

    await flushPromises()

    expect(mocks.loadCategories).toHaveBeenCalledTimes(1)

    await wrapper.get('button').trigger('click')
    await nextTick()
    await flushPromises()

    expect(mocks.loadApiToolProviders).toHaveBeenCalledWith(true)
    expect(mocks.loadBuiltinTools).toHaveBeenCalled()
    expect(wrapper.find('[data-testid="tools-modal"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('关联插件')

    await wrapper.get('button.ml-6').trigger('click')
    await nextTick()
    await flushPromises()

    expect(wrapper.find('[data-testid="tools-modal"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('关联插件')
  })

  it('does not open tool settings for a stale detail response', async () => {
    const wrapper = mountToolsAbilityItem()
    await wrapper.setProps({
      tools: [{
        type: 'builtin_tool',
        provider: { id: 'provider', name: 'provider', label: 'Provider', icon: '', description: '' },
        tool: { id: 'tool', name: 'tool', label: 'Tool', description: '', params: {} },
      }],
    })
    mocks.loadBuiltinTool.mockResolvedValueOnce(false)

    await wrapper.get('button.rounded').trigger('click')
    await flushPromises()

    expect(mocks.loadBuiltinTool).toHaveBeenCalledWith('provider', 'tool')
    expect(wrapper.find('[data-testid="tools-modal"]').exists()).toBe(false)
  })

  it('does not open API tool settings for a stale detail response', async () => {
    const wrapper = mountToolsAbilityItem()
    await wrapper.setProps({
      tools: [{
        type: 'api_tool',
        provider: { id: 'provider', name: 'provider', label: 'Provider', icon: '', description: '' },
        tool: { id: 'tool', name: 'tool', label: 'Tool', description: '', params: {} },
      }],
    })
    mocks.loadApiTool.mockResolvedValueOnce(false)

    await wrapper.get('button.rounded').trigger('click')
    await flushPromises()

    expect(mocks.loadApiTool).toHaveBeenCalledWith('provider', 'tool')
    expect(wrapper.find('[data-testid="tools-modal"]').exists()).toBe(false)
  })

  it('removes only the selected tool when other tools share its provider or name', async () => {
    mocks.builtinTools = [
      { name: 'provider-a', label: 'Provider A', category: 'all', tools: [{ name: 'alpha', label: 'Alpha', params: [] }, { name: 'beta', label: 'Beta', params: [] }] },
      { name: 'provider-b', label: 'Provider B', category: 'all', tools: [{ name: 'alpha', label: 'Alpha', params: [] }] },
    ]
    const selected = [
      { type: 'builtin_tool', provider: { id: 'provider-a', name: 'provider-a' }, tool: { name: 'alpha', params: {} } },
      { type: 'builtin_tool', provider: { id: 'provider-a', name: 'provider-a' }, tool: { name: 'beta', params: {} } },
      { type: 'builtin_tool', provider: { id: 'provider-b', name: 'provider-b' }, tool: { name: 'alpha', params: {} } },
    ]
    const wrapper = mount(ToolsAbilityItem, {
      props: { app_id: 'app-1', tools: selected as never[] },
      global: { stubs: { 'a-collapse-item': collapseItemStub, 'a-button': buttonStub, 'a-modal': modalStub, 'a-avatar': true, 'a-tooltip': true, 'a-form': true, 'a-form-item': true, 'a-input': true, 'a-input-number': true, 'a-select': true, 'a-radio-group': true, 'a-radio': true, 'a-row': true, 'a-col': true, 'a-spin': true, 'a-empty': true, 'a-space': true, 'a-tag': true, 'a-input-search': true, 'a-divider': true, 'router-link': true, 'icon-plus': true, 'icon-settings': true, 'icon-delete': true, 'icon-close': true, 'icon-code': true, 'icon-translate': true, 'icon-apps': true, 'icon-oblique-line': true, 'icon-info-circle': true, 'icon-question-circle': true } },
    })

    await wrapper.get('button').trigger('click')
    await flushPromises()
    await wrapper.findAll('.cursor-pointer').find(item => item.text().includes('内置插件'))!.trigger('click')
    await wrapper.findAll('button').find(button => button.text() === '移除')!.trigger('click')
    await flushPromises()

    const remaining = wrapper.emitted('update:tools')?.at(-1)?.[0] as typeof selected
    expect(remaining.map(tool => [tool.provider.name, tool.tool.name])).toEqual([
      ['provider-a', 'beta'],
      ['provider-b', 'alpha'],
    ])
  })

  it('does not mutate tool props while a settings update is pending', async () => {
    let resolveUpdate!: () => void
    const update = new Promise<void>(resolve => { resolveUpdate = resolve })
    const selected = [{
      type: 'builtin_tool',
      provider: { id: 'provider', name: 'provider', label: 'Provider', icon: '', description: '' },
      tool: { id: 'flag', name: 'flag', label: 'Flag', description: '', params: { enabled: false } },
    }]
    mocks.builtinTool = {
      provider: { name: 'provider', label: 'Provider', description: '' },
      name: 'flag', label: 'Flag', description: '', inputs: [],
      params: [{ name: 'enabled', label: 'Enabled', type: 'boolean', default: false }],
    }
    mocks.loadBuiltinTool.mockResolvedValueOnce(true)
    mocks.updateDraftAppConfig.mockReturnValueOnce(update)
    const wrapper = mountToolsAbilityItem()
    await wrapper.setProps({ tools: selected as never[] })
    await wrapper.get('button.rounded').trigger('click')
    await flushPromises()
    await wrapper.findAll('.cursor-pointer').find(item => item.text().includes('appStudio.abilities.tools.settings'))!.trigger('click')
    wrapper.findComponent(radioGroupStub).vm.$emit('update:modelValue', true)
    await nextTick()

    await wrapper.findAll('button').find(button => button.text() === '保存')!.trigger('click')
    await nextTick()

    expect(selected[0].tool.params).toEqual({ enabled: false })
    expect(mocks.updateDraftAppConfig).toHaveBeenCalledWith('app-1', {
      tools: [expect.objectContaining({ tool_id: 'flag', params: { enabled: true } })],
    })
    resolveUpdate()
    await flushPromises()
  })
})
