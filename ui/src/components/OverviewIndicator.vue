<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PropType } from 'vue'

// 1.定义自定义组件所需数据
const props = defineProps({
  title: { type: String, default: '' },
  help: { type: String, default: '' },
  data: { type: Number as PropType<number | null>, default: 0 },
  unit: { type: String, default: '' },
  pop: { type: Number as PropType<number | null>, default: 0 },
})
const { t, locale } = useI18n()
const resolvedUnit = computed(() => props.unit || (locale.value === 'en-US' ? 'times' : '次'))
</script>

<template>
  <div class="flex flex-col flex-1 gap-3 bg-white border border-gray-200 rounded-lg px-6 py-5">
    <!-- 指标卡标题 -->
    <div class="flex items-center gap-2 text-gray-700">
      <a-avatar shape="circle" :size="32" class="bg-blue-200">
        <!-- 创建命名插槽 -->
        <slot name="icon" />
      </a-avatar>
      <div class="">{{ props.title }}</div>
      <a-tooltip :content="props.help">
        <icon-question-circle />
      </a-tooltip>
    </div>
    <!-- 指标卡数据 -->
    <div class="flex items-baseline gap-4">
      <!-- 数据 -->
      <div class="flex items-baseline gap-1 text-gray-700 font-semibold">
        <div class="text-2xl">
          {{ props.data == null ? '—' : props.data % 1 !== 0 ? props.data.toFixed(2) : props.data.toString() }}
        </div>
        <div class="">{{ resolvedUnit }}</div>
      </div>
      <!-- 环比 -->
      <div class="flex items-center gap-1 text-gray-500 text-xs">
        <div class="">{{ t('chat.overview.periodOverPeriod') }}</div>
        <a-avatar shape="circle" :size="14" class="bg-blue-200">
          <icon-sync class="text-[14px] text-blue-700" />
        </a-avatar>
        <div class="text-blue-700">{{ props.pop == null ? '—' : `${(props.pop * 100).toFixed(2)}%` }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped></style>
