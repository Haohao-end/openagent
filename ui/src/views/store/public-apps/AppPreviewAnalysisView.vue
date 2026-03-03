<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, TooltipComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'
import moment from 'moment'
import { getPublicAppAnalysis } from '@/services/public-app'
import OverviewIndicator from '@/components/OverviewIndicator.vue'

use([GridComponent, LineChart, CanvasRenderer, TooltipComponent])

type TrendField =
  | 'total_messages_trend'
  | 'active_accounts_trend'
  | 'avg_of_conversation_messages_trend'
  | 'cost_consumption_trend'

type TrendCard = {
  key: TrendField
  title: string
  help: string
  unit: string
  color: string
  areaColor: string
  decimals: number
}

type TrendInsight = {
  latest: string
  peak: string
  average: string
}

type OverviewMetric = {
  data: number
  pop: number
}

type TrendMetric = {
  x_axis: number[]
  y_axis: number[]
}

type AppAnalysis = {
  total_messages?: OverviewMetric
  active_accounts?: OverviewMetric
  avg_of_conversation_messages?: OverviewMetric
  token_output_rate?: OverviewMetric
  cost_consumption?: OverviewMetric
  total_messages_trend?: TrendMetric
  active_accounts_trend?: TrendMetric
  avg_of_conversation_messages_trend?: TrendMetric
  cost_consumption_trend?: TrendMetric
}

const route = useRoute()
const getAppAnalysisLoading = ref(false)
const app_analysis = ref<AppAnalysis>({})

// 加载统计分析数据
const loadAppAnalysis = async (app_id: string) => {
  try {
    getAppAnalysisLoading.value = true
    const res = await getPublicAppAnalysis(app_id)
    app_analysis.value = res.data
  } finally {
    getAppAnalysisLoading.value = false
  }
}

const trendCards: TrendCard[] = [
  {
    key: 'total_messages_trend',
    title: '全部会话数',
    help: '反映 AI 每天的会话消息总数，在指定的时间范围内，用户对应用发起的请求总次数，一问一答记一次，用于衡量用户活跃度。',
    unit: '次',
    color: '#2563EB',
    areaColor: 'rgba(37,99,235,0.24)',
    decimals: 0,
  },
  {
    key: 'active_accounts_trend',
    title: '活跃用户数',
    help: '指定的发布渠道和时间范围内，至少完成一轮对话的总使用用户数量，用于衡量应用吸引力。',
    unit: '人',
    color: '#059669',
    areaColor: 'rgba(5,150,105,0.24)',
    decimals: 0,
  },
  {
    key: 'avg_of_conversation_messages_trend',
    title: '平均会话互动数',
    help: '反映每个会话用户的持续沟通次数，如果用户与 AI 进行了 10 轮对话，即为 10，该指标反映了用户粘性。',
    unit: '次',
    color: '#D97706',
    areaColor: 'rgba(217,119,6,0.24)',
    decimals: 2,
  },
  {
    key: 'cost_consumption_trend',
    title: '费用消耗',
    help: '反映每日该应用请求语言模型的 Tokens 花费，用于成本控制。',
    unit: 'RMB',
    color: '#DC2626',
    areaColor: 'rgba(220,38,38,0.22)',
    decimals: 2,
  },
]

const formatFixed = (value: number, decimals = 0) =>
  value.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })

const formatCardValue = (value: number, card: TrendCard) => formatFixed(value, card.decimals)

const formatTooltipValue = (value: number, card: TrendCard) => {
  const base = formatCardValue(value, card)
  if (card.key === 'cost_consumption_trend') {
    return `¥${base}`
  }
  return `${base} ${card.unit}`
}

const formatAxisValue = (value: number, card: TrendCard) => {
  const absValue = Math.abs(value)
  if (absValue >= 10000) {
    const shortValue = (value / 10000).toFixed(1)
    return card.key === 'cost_consumption_trend' ? `¥${shortValue}万` : `${shortValue}万`
  }
  if (absValue >= 1000) {
    const shortValue = (value / 1000).toFixed(1)
    return card.key === 'cost_consumption_trend' ? `¥${shortValue}k` : `${shortValue}k`
  }
  const fixed = card.decimals > 0 ? value.toFixed(card.decimals) : value.toFixed(0)
  return card.key === 'cost_consumption_trend' ? `¥${fixed}` : fixed
}

const buildTrendOption = (card: TrendCard): EChartsOption => {
  const xAxisSource = app_analysis.value?.[card.key]?.x_axis ?? []
  const yAxisSource = app_analysis.value?.[card.key]?.y_axis ?? []
  const xAxis = xAxisSource.map((value: number) => moment.unix(value).format('MM/DD'))
  const fullDate = xAxisSource.map((value: number) => moment.unix(value).format('YYYY-MM-DD'))

  return {
    animationDuration: 800,
    animationEasing: 'cubicOut',
    grid: {
      top: 32,
      right: 20,
      bottom: 40,
      left: 16,
      containLabel: true,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0F172A',
      borderWidth: 0,
      padding: [8, 10],
      textStyle: {
        color: '#FFFFFF',
        fontSize: 12,
      },
      axisPointer: {
        type: 'line',
        lineStyle: {
          color: '#CBD5E1',
          width: 1,
        },
      },
      formatter: (params: unknown) => {
        const firstItem = Array.isArray(params) ? params[0] : params
        const tooltipItem = (firstItem || {}) as {
          dataIndex?: number | string
          data?: number | string
        }
        if (!firstItem) {
          return ''
        }
        const index = Number(tooltipItem.dataIndex ?? 0)
        const value = Number(tooltipItem.data ?? 0)
        return `
          <div style="font-size:12px;color:#CBD5E1;">${fullDate[index] ?? ''}</div>
          <div style="display:flex;align-items:center;gap:6px;margin-top:4px;">
            <span style="width:8px;height:8px;border-radius:9999px;background:${card.color};display:inline-block;"></span>
            <span>${card.title}</span>
            <span style="font-weight:600;">${formatTooltipValue(value, card)}</span>
          </div>
        `
      },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: xAxis,
      axisTick: { show: false },
      axisLine: {
        lineStyle: { color: '#E2E8F0' },
      },
      axisLabel: {
        color: '#64748B',
        fontSize: 11,
        rotate: 0,
        interval: 0,
        margin: 12,
      },
    },
    yAxis: {
      type: 'value',
      axisTick: { show: false },
      axisLine: { show: false },
      splitNumber: 4,
      splitLine: {
        lineStyle: {
          color: '#EEF2F7',
          type: 'dashed',
        },
      },
      axisLabel: {
        color: '#64748B',
        fontSize: 11,
        formatter: (value: number) => formatAxisValue(value, card),
      },
    },
    series: [
      {
        name: card.title,
        type: 'line',
        smooth: 0.35,
        showSymbol: false,
        symbol: 'circle',
        symbolSize: 8,
        data: yAxisSource,
        lineStyle: {
          width: 2.5,
          color: card.color,
        },
        itemStyle: {
          color: card.color,
          borderWidth: 2,
          borderColor: '#FFFFFF',
        },
        emphasis: {
          focus: 'series',
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: card.areaColor },
              { offset: 1, color: 'rgba(255,255,255,0)' },
            ],
          },
        },
      },
    ],
  }
}

const trendOption = computed(() => {
  return trendCards.reduce(
    (acc, card) => {
      acc[card.key] = buildTrendOption(card)
      return acc
    },
    {} as Record<TrendField, EChartsOption>,
  )
})

const trendHasData = computed(() => {
  return trendCards.reduce(
    (acc, card) => {
      const yAxis = app_analysis.value?.[card.key]?.y_axis ?? []
      acc[card.key] = Array.isArray(yAxis) && yAxis.length > 0
      return acc
    },
    {} as Record<TrendField, boolean>,
  )
})

const trendInsights = computed(() => {
  return trendCards.reduce(
    (acc, card) => {
      const values = (app_analysis.value?.[card.key]?.y_axis ?? []).filter((value: unknown) =>
        Number.isFinite(Number(value)),
      ) as number[]
      if (!values.length) {
        acc[card.key] = {
          latest: '--',
          peak: '--',
          average: '--',
        }
        return acc
      }
      const latest = values[values.length - 1]
      const peak = Math.max(...values)
      const average = values.reduce((sum, value) => sum + value, 0) / values.length
      acc[card.key] = {
        latest: formatCardValue(latest, card),
        peak: formatCardValue(peak, card),
        average: formatCardValue(average, card),
      }
      return acc
    },
    {} as Record<TrendField, TrendInsight>,
  )
})

onMounted(() => {
  loadAppAnalysis(String(route.params?.app_id))
})
</script>

<template>
  <div class="analysis-page px-6 py-6 h-full overflow-y-auto scrollbar-w-none">
    <div class="analysis-banner mb-6">
      <div>
        <div class="analysis-banner__title">统计分析看板</div>
        <div class="analysis-banner__desc">
          通过近 7 天会话、活跃与成本趋势，快速洞察应用运营质量和资源消耗变化。
        </div>
      </div>
      <a-tag color="arcoblue" bordered>
        <template #icon>
          <icon-schedule />
        </template>
        数据范围：近 7 天
      </a-tag>
    </div>

    <div class="flex flex-col gap-5 mb-6">
      <div class="section-head">
        <div class="text-base text-gray-700 font-semibold">概览指标</div>
        <div class="text-xs text-gray-500">过去7天关键业务指标</div>
      </div>
      <a-spin :loading="getAppAnalysisLoading">
        <div class="grid gap-4 grid-cols-1 sm:grid-cols-2 xl:grid-cols-5">
          <overview-indicator
            title="全部会话数"
            help="反映 AI 每天的会话消息总数，在指定的时间范围内，用户对应用发起的请求总次数，一问一答记一次，用于衡量用户活跃度。"
            unit="次"
            :data="app_analysis?.total_messages?.data"
            :pop="app_analysis?.total_messages?.pop"
          >
            <template #icon>
              <icon-dashboard class="text-blue-700" />
            </template>
          </overview-indicator>
          <overview-indicator
            title="活跃用户数"
            help="指定的发布渠道和时间范围内，至少完成一轮对话的总使用用户数量，用于衡量应用吸引力。"
            unit="人"
            :data="app_analysis?.active_accounts?.data"
            :pop="app_analysis?.active_accounts?.pop"
          >
            <template #icon>
              <icon-computer class="text-emerald-700" />
            </template>
          </overview-indicator>
          <overview-indicator
            title="平均会话互动数"
            help="反映每个会话用户的持续沟通次数，如果用户与 AI 进行了 10 轮对话，即为 10，该指标反映了用户粘性。"
            unit="次"
            :data="app_analysis?.avg_of_conversation_messages?.data"
            :pop="app_analysis?.avg_of_conversation_messages?.pop"
          >
            <template #icon>
              <icon-bulb class="text-amber-700" />
            </template>
          </overview-indicator>
          <overview-indicator
            title="Token输出速度"
            help="衡量 LLM 的性能，统计 LLM 从请求到输出完毕这段期间内的 Tokens 输出速度。"
            unit="Ts/秒"
            :data="app_analysis?.token_output_rate?.data"
            :pop="app_analysis?.token_output_rate?.pop"
          >
            <template #icon>
              <icon-language class="text-cyan-700" />
            </template>
          </overview-indicator>
          <overview-indicator
            title="费用消耗"
            help="反映每日该应用请求语言模型的 Tokens 花费，用于成本控制。"
            unit="RMB"
            :data="app_analysis?.cost_consumption?.data"
            :pop="app_analysis?.cost_consumption?.pop"
          >
            <template #icon>
              <icon-code class="text-red-700" />
            </template>
          </overview-indicator>
        </div>
      </a-spin>
    </div>

    <div class="flex flex-col gap-5">
      <div class="section-head">
        <div class="text-base text-gray-700 font-semibold">详细指标</div>
        <div class="text-xs text-gray-500">趋势分布与关键统计特征</div>
      </div>
      <a-spin :loading="getAppAnalysisLoading">
        <div class="grid gap-4 grid-cols-1 2xl:grid-cols-2">
          <div
            v-for="trend in trendCards"
            :key="trend.key"
            class="chart-card"
            :style="{
              '--chart-accent': trend.color,
            }"
          >
            <div class="chart-card__head">
              <div class="flex items-center gap-2">
                <div class="chart-card__title">{{ trend.title }}</div>
                <a-tooltip :content="trend.help">
                  <icon-question-circle-fill />
                </a-tooltip>
              </div>
              <a-tag bordered size="small">近7天</a-tag>
            </div>
            <div class="chart-card__summary">
              <div class="chart-card__value">
                {{ trendInsights[trend.key].latest }}
                <span class="chart-card__unit">{{ trend.unit }}</span>
              </div>
              <div class="chart-card__meta">
                峰值 {{ trendInsights[trend.key].peak }} · 均值 {{ trendInsights[trend.key].average }}
              </div>
            </div>
            <div class="chart-card__body">
              <v-chart
                v-if="trendHasData[trend.key]"
                :init-options="{ renderer: 'canvas' }"
                :option="trendOption[trend.key]"
                :autoresize="true"
                class="h-full w-full"
              />
              <a-empty v-else class="chart-empty" description="暂无趋势数据" />
            </div>
          </div>
        </div>
      </a-spin>
    </div>
  </div>
</template>

<style scoped>
.analysis-page {
  background:
    radial-gradient(circle at 0% 0%, rgba(59, 130, 246, 0.1) 0%, rgba(241, 245, 249, 0) 45%),
    linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
}

.analysis-banner {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding: 16px 20px;
  border-radius: 14px;
  border: 1px solid #dbe2f1;
  background: linear-gradient(120deg, #ffffff 0%, #f8fbff 100%);
}

.analysis-banner__title {
  color: #0f172a;
  font-size: 18px;
  line-height: 26px;
  font-weight: 700;
}

.analysis-banner__desc {
  margin-top: 4px;
  color: #475569;
  font-size: 13px;
  line-height: 20px;
}

.section-head {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: baseline;
}

.chart-card {
  display: flex;
  flex-direction: column;
  min-height: 380px;
  padding: 20px;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.chart-card:hover {
  transform: translateY(-2px);
  border-color: var(--chart-accent);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
}

.chart-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 6px;
}

.chart-card__title {
  color: #334155;
  font-size: 15px;
  line-height: 22px;
  font-weight: 700;
}

.chart-card__summary {
  margin-bottom: 10px;
}

.chart-card__value {
  color: #0f172a;
  font-size: 24px;
  line-height: 32px;
  font-weight: 700;
}

.chart-card__unit {
  margin-left: 6px;
  color: #64748b;
  font-size: 13px;
  line-height: 18px;
  font-weight: 500;
}

.chart-card__meta {
  color: #64748b;
  font-size: 12px;
  line-height: 18px;
}

.chart-card__body {
  flex: 1;
  min-height: 240px;
}

.chart-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 768px) {
  .analysis-banner {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
