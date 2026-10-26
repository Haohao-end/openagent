import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AnalysisView from '../AnalysisView.vue'

const mocks = vi.hoisted(() => ({
  loadAppAnalysis: vi.fn(),
  appAnalysis: {
    total_messages: { data: 128, pop: 12 },
    active_accounts: { data: 16, pop: 4 },
    avg_of_conversation_messages: { data: 4.2, pop: 0.3 },
    avg_latency: { data: 1.5, pop: 0.2 },
    token_output_rate: { data: 1280, pop: 18 },
    cost_consumption: { data: 36.5, pop: 2.1 },
    total_messages_trend: {
      x_axis: [1717526400, 1717612800],
      y_axis: [32, 36],
    },
    active_accounts_trend: {
      x_axis: [1717526400, 1717612800],
      y_axis: [8, 10],
    },
    avg_of_conversation_messages_trend: {
      x_axis: [1717526400, 1717612800],
      y_axis: [3.2, 4.2],
    },
    cost_consumption_trend: {
      x_axis: [1717526400, 1717612800],
      y_axis: [18.5, 20.8],
    },
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: {
      app_id: 'app-1',
    },
  }),
}))

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: {
      option: { type: Object, default: () => ({}) },
      initOptions: { type: Object, default: () => ({}) },
      autoresize: { type: Boolean, default: false },
    },
    template: '<div class="v-chart-stub" />',
  },
}))

vi.mock('vue-i18n', () => {
  const translations: Record<string, string> = {
    'appStudio.analysis.title': '统计分析看板',
    'appStudio.analysis.description':
      '通过近 7 天会话、活跃与成本趋势，快速洞察应用运营质量和资源消耗变化。',
    'appStudio.analysis.recentSevenDays': '数据范围：近 7 天',
    'appStudio.analysis.overviewTitle': '概览指标',
    'appStudio.analysis.overviewDescription': '过去 7 天关键业务指标',
    'appStudio.analysis.detailsTitle': '详细指标',
    'appStudio.analysis.detailsDescription': '趋势分布与关键统计特征',
    'appStudio.analysis.cardPeriod': '近 7 天',
    'appStudio.analysis.peakAndAverage': '峰值 {peak} · 均值 {average}',
    'appStudio.analysis.noTrendData': '暂无趋势数据',
    'appStudio.analysis.trendCards.totalMessages.title': '全部会话数',
    'appStudio.analysis.trendCards.totalMessages.help': '全部会话数说明',
    'appStudio.analysis.trendCards.totalMessages.unit': '次',
    'appStudio.analysis.trendCards.activeAccounts.title': '活跃用户数',
    'appStudio.analysis.trendCards.activeAccounts.help': '活跃用户数说明',
    'appStudio.analysis.trendCards.activeAccounts.unit': '人',
    'appStudio.analysis.trendCards.avgConversationMessages.title': '平均会话互动数',
    'appStudio.analysis.trendCards.avgConversationMessages.help': '平均会话互动数说明',
    'appStudio.analysis.trendCards.avgConversationMessages.unit': '次',
    'appStudio.analysis.trendCards.averageLatency.title': '平均响应耗时',
    'appStudio.analysis.trendCards.averageLatency.help': '平均响应耗时说明',
    'appStudio.analysis.trendCards.averageLatency.unit': '秒',
    'appStudio.analysis.trendCards.tokenOutputRate.title': 'Token 输出速度',
    'appStudio.analysis.trendCards.tokenOutputRate.help': 'Token 输出速度说明',
    'appStudio.analysis.trendCards.tokenOutputRate.unit': 'Ts/秒',
    'appStudio.analysis.trendCards.costConsumption.title': '费用消耗',
    'appStudio.analysis.trendCards.costConsumption.help': '费用消耗说明',
    'appStudio.analysis.trendCards.costConsumption.unit': 'RMB',
  }

  const translate = (key: string, params?: Record<string, string | number>) => {
    let value = translations[key] || key
    if (params) {
      Object.entries(params).forEach(([paramKey, paramValue]) => {
        value = value.replace(`{${paramKey}}`, String(paramValue))
      })
    }
    return value
  }

  return {
    useI18n: () => ({
      t: translate,
      locale: { value: 'zh-CN' },
    }),
  }
})

vi.mock('@/hooks/use-analysis', async () => {
  const { ref } = await import('vue')
  return {
    useGetAppAnalysis: () => ({
      loading: ref(false),
      app_analysis: ref(mocks.appAnalysis),
      loadAppAnalysis: mocks.loadAppAnalysis,
    }),
  }
})

const slotStub = {
  template: '<div><slot /><slot name="icon" /></div>',
}

describe('AnalysisView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the analysis dashboard without intro banner copy', async () => {
    const wrapper = mount(AnalysisView, {
      global: {
        stubs: {
          'overview-indicator': {
            props: {
              title: { type: String, default: '' },
            },
            template: '<div class="overview-indicator">{{ title }}<slot name="icon" /></div>',
          },
          'a-spin': slotStub,
          'a-tooltip': slotStub,
          'a-empty': slotStub,
          'a-tag': slotStub,
          'icon-dashboard': true,
          'icon-computer': true,
          'icon-bulb': true,
          'icon-clock-circle': true,
          'icon-language': true,
          'icon-code': true,
          'icon-question-circle-fill': true,
        },
      },
    })

    await flushPromises()

    expect(mocks.loadAppAnalysis).toHaveBeenCalledWith('app-1')
    expect(wrapper.text()).toContain('概览指标')
    expect(wrapper.text()).toContain('详细指标')
    expect(wrapper.text()).toContain('平均响应耗时')
    expect(wrapper.text()).not.toContain('统计分析看板')
    expect(wrapper.text()).not.toContain('通过近 7 天会话、活跃与成本趋势，快速洞察应用运营质量和资源消耗变化。')
    expect(wrapper.text()).not.toContain('数据范围：近 7 天')
    expect(wrapper.text()).not.toContain('过去 7 天关键业务指标')
    expect(wrapper.text()).not.toContain('趋势分布与关键统计特征')
    expect(wrapper.text()).not.toContain('近 7 天')
  })
})
