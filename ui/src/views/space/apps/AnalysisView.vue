<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, TooltipComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'
import moment from 'moment'
import { useGetAppAnalysis } from '@/hooks/use-analysis'
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

const route = useRoute()
const { t, locale } = useI18n()
const { loading: getAppAnalysisLoading, app_analysis, loadAppAnalysis } = useGetAppAnalysis()

const trendCards = computed<TrendCard[]>(() => [
  {
    key: 'total_messages_trend',
    title: t('appStudio.analysis.trendCards.totalMessages.title'),
    help: t('appStudio.analysis.trendCards.totalMessages.help'),
    unit: t('appStudio.analysis.trendCards.totalMessages.unit'),
    color: '#2563EB',
    areaColor: 'rgba(37,99,235,0.24)',
    decimals: 0,
  },
  {
    key: 'active_accounts_trend',
    title: t('appStudio.analysis.trendCards.activeAccounts.title'),
    help: t('appStudio.analysis.trendCards.activeAccounts.help'),
    unit: t('appStudio.analysis.trendCards.activeAccounts.unit'),
    color: '#059669',
    areaColor: 'rgba(5,150,105,0.24)',
    decimals: 0,
  },
  {
    key: 'avg_of_conversation_messages_trend',
    title: t('appStudio.analysis.trendCards.avgConversationMessages.title'),
    help: t('appStudio.analysis.trendCards.avgConversationMessages.help'),
    unit: t('appStudio.analysis.trendCards.avgConversationMessages.unit'),
    color: '#D97706',
    areaColor: 'rgba(217,119,6,0.24)',
    decimals: 2,
  },
  {
    key: 'cost_consumption_trend',
    title: t('appStudio.analysis.trendCards.costConsumption.title'),
    help: t('appStudio.analysis.trendCards.costConsumption.help'),
    unit: t('appStudio.analysis.trendCards.costConsumption.unit'),
    color: '#DC2626',
    areaColor: 'rgba(220,38,38,0.22)',
    decimals: 2,
  },
])

const formatFixed = (value: number, decimals = 0) =>
  value.toLocaleString(locale.value, {
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
  const compactValue = new Intl.NumberFormat(locale.value, {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value)
  return card.key === 'cost_consumption_trend' ? `¥${compactValue}` : compactValue
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
  return trendCards.value.reduce(
    (acc, card) => {
      acc[card.key] = buildTrendOption(card)
      return acc
    },
    {} as Record<TrendField, EChartsOption>,
  )
})

const trendHasData = computed(() => {
  return trendCards.value.reduce(
    (acc, card) => {
      const yAxis = app_analysis.value?.[card.key]?.y_axis ?? []
      acc[card.key] = Array.isArray(yAxis) && yAxis.length > 0
      return acc
    },
    {} as Record<TrendField, boolean>,
  )
})

const trendInsights = computed(() => {
  return trendCards.value.reduce(
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
  <div class="analysis-page flex h-full min-h-0 w-full flex-col overflow-hidden">
    <div class="analysis-page__scroll flex-1 min-h-0 overflow-y-auto scrollbar-w-none px-6 py-6">
      <div class="flex flex-col gap-5 mb-6">
      <div class="section-head">
        <div class="text-base text-gray-700 font-semibold">{{ t('appStudio.analysis.overviewTitle') }}</div>
      </div>
      <a-spin :loading="getAppAnalysisLoading">
        <div class="grid gap-4 grid-cols-1 sm:grid-cols-2 xl:grid-cols-6">
          <overview-indicator
            :title="t('appStudio.analysis.trendCards.totalMessages.title')"
            :help="t('appStudio.analysis.trendCards.totalMessages.help')"
            :unit="t('appStudio.analysis.trendCards.totalMessages.unit')"
            :data="app_analysis?.total_messages?.data"
            :pop="app_analysis?.total_messages?.pop"
          >
            <template #icon>
              <icon-dashboard class="text-blue-700" />
            </template>
          </overview-indicator>
          <overview-indicator
            :title="t('appStudio.analysis.trendCards.averageLatency.title')"
            :help="t('appStudio.analysis.trendCards.averageLatency.help')"
            :unit="t('appStudio.analysis.trendCards.averageLatency.unit')"
            :data="app_analysis?.avg_latency?.data"
            :pop="app_analysis?.avg_latency?.pop"
          >
            <template #icon>
              <icon-clock-circle class="text-violet-700" />
            </template>
          </overview-indicator>
          <overview-indicator
            :title="t('appStudio.analysis.trendCards.activeAccounts.title')"
            :help="t('appStudio.analysis.trendCards.activeAccounts.help')"
            :unit="t('appStudio.analysis.trendCards.activeAccounts.unit')"
            :data="app_analysis?.active_accounts?.data"
            :pop="app_analysis?.active_accounts?.pop"
          >
            <template #icon>
              <icon-computer class="text-emerald-700" />
            </template>
          </overview-indicator>
          <overview-indicator
            :title="t('appStudio.analysis.trendCards.avgConversationMessages.title')"
            :help="t('appStudio.analysis.trendCards.avgConversationMessages.help')"
            :unit="t('appStudio.analysis.trendCards.avgConversationMessages.unit')"
            :data="app_analysis?.avg_of_conversation_messages?.data"
            :pop="app_analysis?.avg_of_conversation_messages?.pop"
          >
            <template #icon>
              <icon-bulb class="text-amber-700" />
            </template>
          </overview-indicator>
          <overview-indicator
            :title="t('appStudio.analysis.trendCards.tokenOutputRate.title')"
            :help="t('appStudio.analysis.trendCards.tokenOutputRate.help')"
            :unit="t('appStudio.analysis.trendCards.tokenOutputRate.unit')"
            :data="app_analysis?.token_output_rate?.data"
            :pop="app_analysis?.token_output_rate?.pop"
          >
            <template #icon>
              <icon-language class="text-cyan-700" />
            </template>
          </overview-indicator>
          <overview-indicator
            :title="t('appStudio.analysis.trendCards.costConsumption.title')"
            :help="t('appStudio.analysis.trendCards.costConsumption.help')"
            :unit="t('appStudio.analysis.trendCards.costConsumption.unit')"
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
        <div class="text-base text-gray-700 font-semibold">{{ t('appStudio.analysis.detailsTitle') }}</div>
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
            </div>
            <div class="chart-card__summary">
              <div class="chart-card__value">
                {{ trendInsights[trend.key].latest }}
                <span class="chart-card__unit">{{ trend.unit }}</span>
              </div>
              <div class="chart-card__meta">
                {{ t('appStudio.analysis.peakAndAverage', { peak: trendInsights[trend.key].peak, average: trendInsights[trend.key].average }) }}
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
              <a-empty v-else class="chart-empty" :description="t('appStudio.analysis.noTrendData')" />
            </div>
          </div>
        </div>
      </a-spin>
      </div>
    </div>
  </div>
</template>

<style scoped>
.analysis-page {
  background:
    radial-gradient(circle at 0% 0%, rgba(59, 130, 246, 0.1) 0%, rgba(241, 245, 249, 0) 45%),
    linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
}

.analysis-page__scroll {
  min-width: 0;
}

.section-head {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
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

</style>
