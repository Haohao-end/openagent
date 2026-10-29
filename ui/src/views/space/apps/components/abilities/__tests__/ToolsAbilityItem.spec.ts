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
    builtin_tool: ref({
      provider: {
        name: '',
        label: '',
        description: '',
      },
      name: '',
      label: '',
      description: '',
      inputs: [],
      params: [],
    }),
    loadBuiltinTool: mocks.loadBuiltinTool,
  }),
  useGetBuiltinTools: () => ({
    builtin_tools: ref([]),
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
        'a-form': true,
        'a-form-item': true,
        'a-input': true,
        'a-input-number': true,
        'a-select': true,
        'a-radio-group': true,
        'a-radio': true,
        'a-row': true,
        'a-col': true,
        'a-spin': true,
        'a-empty': true,
        'a-space': true,
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
})
