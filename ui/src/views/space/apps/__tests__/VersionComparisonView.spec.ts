import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import VersionComparisonView from '../VersionComparisonView.vue'
import * as appService from '@/services/app'

const mocks = vi.hoisted(() => ({
  route: {
    params: {
      app_id: 'app-1',
    },
  },
  mockMessage: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

const mockReactiveRoute = reactive(mocks.route)

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mockReactiveRoute,
  }
})

vi.mock('@arco-design/web-vue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@arco-design/web-vue')>()
  return {
    ...actual,
    Message: mocks.mockMessage,
  }
})

vi.mock('@/services/app', async () => {
  const actual = await vi.importActual<typeof import('@/services/app')>('@/services/app')
  return {
    ...actual,
    getVersions: vi.fn(),
  }
})

vi.mock('@/utils/time-formatter', () => ({
  formatTimestampLong: (value: number) => `时间-${value}`,
}))

const versionComparisonSource = readFileSync(
  resolve(process.cwd(), 'src/views/space/apps/VersionComparisonView.vue'),
  'utf8',
)

const slotStub = {
  props: ['color', 'size', 'bordered', 'loading', 'placeholder', 'modelValue', 'value'],
  template: '<div><slot /></div>',
}

const switchStub = {
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template:
    '<button data-testid="changed-switch" type="button" @click="$emit(\'update:modelValue\', !modelValue)">切换</button>',
}

const emptyStub = {
  props: ['description'],
  template: '<div>{{ description }}</div>',
}

const buildVersion = (overrides: Record<string, any> = {}) => ({
  id: 'draft-version-id',
  app_id: 'app-1',
  version: 0,
  config_type: 'draft',
  is_current_published: false,
  label: '草稿',
  summary: '当前草稿版本',
  created_at: 1710000000,
  updated_at: 1710000100,
  config: {
    model_config: {
      provider: 'deepseek',
      model: 'deepseek-chat',
      parameters: {
        temperature: 1,
        top_p: 1,
        max_tokens: 8000,
      },
    },
    dialog_round: 8,
    preset_prompt: '你是一名企业知识库助手，请先理解用户问题再回答。',
    tools: [
      {
        provider: { id: 'provider-1', name: 'search', label: '搜索服务' },
        tool: { id: 'tool-1', name: 'weather-query', label: '天气查询' },
      },
    ],
    workflows: [{ id: 'workflow-1', name: '工单分流', description: '自动分流工单。' }],
    datasets: [{ id: 'dataset-1', name: '产品知识库', description: '售前售后资料。' }],
    retrieval_config: {
      retrieval_strategy: 'semantic',
      k: 4,
      score: 0.8,
    },
    long_term_memory: { enable: true },
    opening_statement: '你好，我可以帮你查询产品信息。',
    opening_questions: ['你们支持哪些模型？'],
    speech_to_text: { enable: false },
    text_to_speech: { enable: true, voice: 'alloy', auto_play: true },
    suggested_after_answer: { enable: true },
    review_config: {
      enable: true,
      keywords: ['退款', '投诉'],
      inputs_config: { enable: true, preset_response: '请联系人工客服。' },
      outputs_config: { enable: false },
    },
  },
  ...overrides,
})

const mountView = async () => {
  const wrapper = mount(VersionComparisonView, {
    props: {
      app: {
        id: 'app-1',
        name: '企业助手',
      },
    },
    global: {
      stubs: {
        'a-spin': slotStub,
        'a-select': slotStub,
        'a-option': slotStub,
        'a-tag': slotStub,
        'a-avatar': slotStub,
        'a-switch': switchStub,
        'a-empty': emptyStub,
        'icon-apps': true,
        'icon-storage': true,
      },
    },
  })

  await flushPromises()
  return wrapper
}

describe('VersionComparisonView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockReactiveRoute.params.app_id = 'app-1'
  })

  it('keeps the comparison shell full width and the scroll container stable', () => {
    expect(versionComparisonSource).toContain('<a-spin :loading="loading" class="h-full min-h-0 w-full">')
    expect(versionComparisonSource).toContain(
      'class="h-full min-h-0 overflow-y-scroll overflow-x-hidden scrollbar-w-none"',
    )
  })

  it('renders structured compare cards instead of raw JSON blocks', async () => {
    vi.mocked(appService.getVersions).mockResolvedValue({
      data: {
        list: [
          buildVersion(),
          buildVersion({
            id: 'published-version-id',
            version: 3,
            config_type: 'published',
            is_current_published: true,
            label: '版本 #003',
            summary: '当前线上版本',
            created_at: 1700000000,
            updated_at: 1700000100,
            config: {
              model_config: {
                provider: 'deepseek',
                model: 'deepseek-reasoner',
                parameters: {
                  temperature: 1,
                  top_p: 0.95,
                  max_tokens: 8000,
                },
              },
              dialog_round: 8,
              preset_prompt: '你是一名线上客服助手，请先回答常见问题。',
              tools: [
                {
                  provider: { id: 'provider-1', name: 'search', label: '搜索服务' },
                  tool: { id: 'tool-1', name: 'weather-query', label: '天气查询' },
                },
              ],
              workflows: [{ id: 'workflow-1', name: '工单分流', description: '自动分流工单。' }],
              datasets: [{ id: 'dataset-1', name: '产品知识库', description: '售前售后资料。' }],
              retrieval_config: {
                retrieval_strategy: 'semantic',
                k: 6,
                score: 0.82,
              },
              long_term_memory: { enable: false },
              opening_statement: '欢迎使用线上客服。',
              opening_questions: ['怎么联系客服？'],
              speech_to_text: { enable: true },
              text_to_speech: { enable: false, voice: 'alloy', auto_play: false },
              suggested_after_answer: { enable: false },
              review_config: {
                enable: true,
                keywords: ['退款'],
                inputs_config: { enable: true, preset_response: '请联系人工客服。' },
                outputs_config: { enable: true },
              },
            },
          }),
        ],
      },
    } as never)

    const wrapper = await mountView()
    const scrollContainer = wrapper.get('[data-testid="versions-scroll-container"]')

    expect(appService.getVersions).toHaveBeenCalledWith('app-1')
    expect(scrollContainer.text()).toContain('版本对比')
    expect(scrollContainer.text()).toContain('对比版本 A')
    expect(scrollContainer.text()).toContain('对比版本 B')
    expect(wrapper.text()).toContain('模型 deepseek-chat')
    expect(wrapper.text()).toContain('提供方 deepseek')
    expect(wrapper.text()).toContain('最大输出')
    expect(wrapper.text()).toContain('搜索服务 / 天气查询')
    expect(wrapper.text()).toContain('产品知识库')
    expect(wrapper.text()).toContain('内容审核')
    expect(wrapper.text()).toContain('扩展插件')
    expect(wrapper.html()).not.toContain('<pre')
    expect(wrapper.text()).not.toContain('"model":')
    expect(wrapper.text()).not.toContain('左侧版本')
    expect(wrapper.text()).not.toContain('右侧版本')
  })

  it('hides unchanged sections when only-changed mode is enabled and keeps a single hidden-scroll container', async () => {
    vi.mocked(appService.getVersions).mockResolvedValue({
      data: {
        list: [
          buildVersion(),
          buildVersion({
            id: 'published-version-id',
            version: 3,
            config_type: 'published',
            is_current_published: true,
            label: '版本 #003',
            summary: '当前线上版本',
            config: {
              model_config: {
                provider: 'deepseek',
                model: 'deepseek-reasoner',
                parameters: {
                  temperature: 1,
                  top_p: 0.95,
                  max_tokens: 8000,
                },
              },
              dialog_round: 8,
              preset_prompt: '你是一名线上客服助手，请先回答常见问题。',
              tools: [],
              workflows: [],
              datasets: [],
              retrieval_config: {
                retrieval_strategy: 'semantic',
                k: 4,
                score: 0.8,
              },
              long_term_memory: { enable: false },
              opening_statement: '',
              opening_questions: [],
              speech_to_text: { enable: false },
              text_to_speech: { enable: false, voice: 'alloy', auto_play: false },
              suggested_after_answer: { enable: false },
              review_config: {
                enable: false,
                keywords: [],
                inputs_config: { enable: false, preset_response: '' },
                outputs_config: { enable: false },
              },
            },
          }),
        ],
      },
    } as never)

    const wrapper = await mountView()

    const scrollContainer = wrapper.get('[data-testid="versions-scroll-container"]')
    expect(scrollContainer.classes()).toContain('overflow-y-scroll')
    expect(scrollContainer.classes()).toContain('overflow-x-hidden')
    expect(scrollContainer.classes()).toContain('scrollbar-w-none')
    expect(scrollContainer.classes()).not.toContain('overflow-auto')
    expect(scrollContainer.classes()).not.toContain('overflow-y-auto')

    expect(wrapper.find('[data-testid="comparison-section-dialog_round"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="comparison-section-model_config"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('已修改')
    expect(wrapper.text()).toContain('已移除')
    expect(wrapper.findAll('[data-testid="field-diff-model_config-top_p"]').length).toBeGreaterThan(0)
    expect(wrapper.findAll('[data-testid="field-diff-retrieval_config-k"]').length).toBeGreaterThan(0)

    await wrapper.get('[data-testid="changed-switch"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="comparison-section-dialog_round"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="comparison-section-model_config"]').exists()).toBe(true)
  })

  it('does not reset manual version selections when a superseded older request fails or resolves', async () => {
    let rejectA!: (error: Error) => void
    let resolveB!: (value: any) => void
    const promiseA = new Promise((_, reject) => { rejectA = reject })
    const promiseB = new Promise((resolve) => { resolveB = resolve })

    mockReactiveRoute.params.app_id = 'app-A'
    vi.mocked(appService.getVersions).mockImplementation((appId) => {
      if (appId === 'app-A') return promiseA as never
      if (appId === 'app-B') return promiseB as never
      return Promise.resolve({ data: { list: [] } }) as never
    })

    const wrapper = mount(VersionComparisonView, {
      props: {
        app: {
          id: 'app-A',
          name: '应用 A',
        },
      },
      global: {
        stubs: {
          'a-spin': slotStub,
          'a-select': slotStub,
          'a-option': slotStub,
          'a-tag': slotStub,
          'a-avatar': slotStub,
          'a-switch': switchStub,
          'a-empty': emptyStub,
          'icon-apps': true,
          'icon-storage': true,
        },
      },
    })
    await flushPromises()

    // 路由切换至 app-B
    mockReactiveRoute.params.app_id = 'app-B'
    await flushPromises()

    // app-B 加载成功
    resolveB({
      data: {
        list: [
          buildVersion({ id: 'b-v1', label: 'V1', is_current_published: false }),
          buildVersion({ id: 'b-v2', label: 'V2', is_current_published: true }),
          buildVersion({ id: 'b-v3', label: 'V3', is_current_published: false }),
        ],
      },
    })
    await flushPromises()

    expect((wrapper.vm as any).leftVersionId).toBe('b-v1')
    expect((wrapper.vm as any).rightVersionId).toBe('b-v2')

    // 用户手动选择对比版本
    ;(wrapper.vm as any).leftVersionId = 'b-v3'
    ;(wrapper.vm as any).rightVersionId = 'b-v3'

    // app-A 旧请求失败
    rejectA(new Error('app-A network error'))
    await flushPromises()

    // 用户选择不被重置，且没有弹出 app-A 的错误提示
    expect((wrapper.vm as any).leftVersionId).toBe('b-v3')
    expect((wrapper.vm as any).rightVersionId).toBe('b-v3')
    expect(mocks.mockMessage.error).not.toHaveBeenCalled()
  })

  it('shows error feedback when current request fails and keeps selection empty', async () => {
    mockReactiveRoute.params.app_id = 'app-error'
    vi.mocked(appService.getVersions).mockRejectedValueOnce(new Error('获取版本失败'))

    const wrapper = mount(VersionComparisonView, {
      props: {
        app: {
          id: 'app-error',
          name: '错误应用',
        },
      },
      global: {
        stubs: {
          'a-spin': slotStub,
          'a-select': slotStub,
          'a-option': slotStub,
          'a-tag': slotStub,
          'a-avatar': slotStub,
          'a-switch': switchStub,
          'a-empty': emptyStub,
          'icon-apps': true,
          'icon-storage': true,
        },
      },
    })
    await flushPromises()

    expect(mocks.mockMessage.error).toHaveBeenCalledWith('获取版本失败')
    expect((wrapper.vm as any).leftVersionId).toBe('')
    expect((wrapper.vm as any).rightVersionId).toBe('')
  })
})
