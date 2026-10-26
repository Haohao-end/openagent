<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  buildPromptCompareDiff,
  getPromptCompareLatencyDelta,
} from '../utils/prompt-compare-diff'

const props = defineProps<{
  baselineAnswer: string
  candidateAnswer: string
  baselineLatency: number
  candidateLatency: number
}>()

const { t } = useI18n()
const baselineSegments = computed(() =>
  buildPromptCompareDiff(props.baselineAnswer, props.candidateAnswer, 'baseline'),
)
const candidateSegments = computed(() =>
  buildPromptCompareDiff(props.baselineAnswer, props.candidateAnswer, 'candidate'),
)
const latencyDelta = computed(() =>
  getPromptCompareLatencyDelta(props.baselineLatency, props.candidateLatency),
)
const formattedLatencyDelta = computed(() => {
  const sign = latencyDelta.value > 0 ? '+' : ''
  return `${sign}${latencyDelta.value.toFixed(2)}s`
})
</script>

<template>
  <details class="border-t border-gray-100 bg-white px-4 py-2" data-testid="prompt-compare-diff">
    <summary
      class="flex cursor-pointer list-none items-center justify-between gap-3 text-xs text-gray-600"
    >
      <span class="font-semibold">{{ t('appStudio.promptCompare.outputDiff') }}</span>
      <span>{{ t('appStudio.promptCompare.elapsedDiff', { value: formattedLatencyDelta }) }}</span>
    </summary>
    <div class="mt-2 grid grid-cols-2 gap-3 text-xs">
      <section class="min-w-0">
        <h4 class="mb-1 font-medium text-gray-500">
          {{ t('appStudio.promptCompare.baselineTitle') }}
        </h4>
        <p v-if="!baselineAnswer" class="rounded bg-gray-50 p-2 text-gray-500">
          {{ t('appStudio.promptCompare.emptyOutput') }}
        </p>
        <p v-else class="whitespace-pre-wrap break-words rounded bg-gray-50 p-2 text-gray-700">
          <template v-for="(segment, index) in baselineSegments" :key="`baseline-${index}`">
            <del v-if="segment.type === 'removed'" class="bg-red-100 text-red-800">
              {{ segment.text }}
            </del>
            <span v-else>{{ segment.text }}</span>
          </template>
        </p>
      </section>
      <section class="min-w-0">
        <h4 class="mb-1 font-medium text-gray-500">
          {{ t('appStudio.promptCompare.candidateTitle') }}
        </h4>
        <p v-if="!candidateAnswer" class="rounded bg-gray-50 p-2 text-gray-500">
          {{ t('appStudio.promptCompare.emptyOutput') }}
        </p>
        <p v-else class="whitespace-pre-wrap break-words rounded bg-gray-50 p-2 text-gray-700">
          <template v-for="(segment, index) in candidateSegments" :key="`candidate-${index}`">
            <ins v-if="segment.type === 'added'" class="bg-green-100 text-green-800 no-underline">
              {{ segment.text }}
            </ins>
            <span v-else>{{ segment.text }}</span>
          </template>
        </p>
      </section>
    </div>
  </details>
</template>
