<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Message } from '@arco-design/web-vue'
import { useCompareMessages } from '@/hooks/use-conversation'
import { getErrorMessage } from '@/utils/error'

const { t } = useI18n()
const visible = ref(false)
const baseMessageId = ref('')
const { loading, comparison, loadComparison, clearComparison } = useCompareMessages()

const open = (message_id: string) => {
  baseMessageId.value = message_id
  visible.value = true
}

const handleCompare = async (targetMessageId: string) => {
  try {
    await loadComparison(targetMessageId, baseMessageId.value)
  } catch (error) {
    Message.error(getErrorMessage(error, t('chat.compareMessages.loadFailed')))
  }
}

const close = () => {
  visible.value = false
  clearComparison()
}

const formatNumber = (val: number | undefined | null) => {
  if (val === undefined || val === null) return '-'
  return val > 0 ? `+${val}` : `${val}`
}

const diffRows = computed(() => {
  if (!comparison.value) return []
  const { target, base, diff } = comparison.value
  return [
    {
      metric: t('chat.compareMessages.status'),
      target: target.status,
      base: base.status,
      diff: diff.status_changed ? t('chat.compareMessages.changed') : t('chat.compareMessages.same'),
    },
    {
      metric: t('chat.compareMessages.latency'),
      target: `${target.latency}s`,
      base: `${base.latency}s`,
      diff: formatNumber(diff.latency_diff) + 's',
    },
    {
      metric: t('chat.compareMessages.tokens'),
      target: target.total_token_count,
      base: base.total_token_count,
      diff: formatNumber(diff.total_token_count_diff),
    },
    {
      metric: t('chat.compareMessages.price'),
      target: `¥${target.total_price}`,
      base: `¥${base.total_price}`,
      diff: formatNumber(diff.total_price_diff),
    },
    {
      metric: t('chat.compareMessages.answerLength'),
      target: target.answer_length,
      base: base.answer_length,
      diff: formatNumber(diff.answer_length_diff),
    },
    {
      metric: t('chat.compareMessages.error'),
      target: target.error || '-',
      base: base.error || '-',
      diff: diff.error_changed ? t('chat.compareMessages.changed') : t('chat.compareMessages.same'),
    },
  ]
})

defineExpose({ open, handleCompare })
</script>

<template>
  <a-modal
    v-model:visible="visible"
    :title="t('chat.compareMessages.title')"
    :footer="false"
    width="680px"
    @cancel="close"
  >
    <a-spin :loading="loading" class="w-full">
      <div v-if="comparison" class="flex flex-col gap-4">
        <div class="grid grid-cols-4 gap-2 text-xs font-semibold text-gray-500 pb-2 border-b">
          <div>{{ t('chat.compareMessages.metric') }}</div>
          <div>{{ t('chat.compareMessages.base') }}</div>
          <div>{{ t('chat.compareMessages.target') }}</div>
          <div>{{ t('chat.compareMessages.diff') }}</div>
        </div>
        <div
          v-for="row in diffRows"
          :key="row.metric"
          class="grid grid-cols-4 gap-2 text-sm text-gray-700 py-1"
        >
          <div class="font-medium text-gray-900">{{ row.metric }}</div>
          <div>{{ row.base }}</div>
          <div>{{ row.target }}</div>
          <div :class="row.diff.startsWith('+') ? 'text-rose-600' : row.diff.startsWith('-') ? 'text-emerald-600' : 'text-gray-500'">
            {{ row.diff }}
          </div>
        </div>

        <div
          v-if="comparison.base.answer !== undefined || comparison.target.answer !== undefined"
          class="flex flex-col gap-2 pt-2 border-t"
        >
          <div class="flex items-center justify-between text-xs font-semibold text-gray-700">
            <span>{{ t('chat.compareMessages.answerComparison') }}</span>
            <span
              :class="comparison.diff.answer_match ? 'text-emerald-600 bg-emerald-50' : 'text-amber-600 bg-amber-50'"
              class="px-2 py-0.5 rounded font-medium text-xs"
            >
              {{ comparison.diff.answer_match ? t('chat.compareMessages.answerMatch') : t('chat.compareMessages.answerMismatch') }}
            </span>
          </div>
          <div class="grid grid-cols-2 gap-3 text-xs">
            <div class="flex flex-col gap-1 p-2.5 bg-gray-50 border rounded">
              <div class="font-semibold text-gray-600">{{ t('chat.compareMessages.base') }}</div>
              <div class="text-gray-800 whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                {{ comparison.base.answer || '-' }}
              </div>
            </div>
            <div class="flex flex-col gap-1 p-2.5 bg-gray-50 border rounded">
              <div class="font-semibold text-gray-600">{{ t('chat.compareMessages.target') }}</div>
              <div class="text-gray-800 whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                {{ comparison.target.answer || '-' }}
              </div>
            </div>
          </div>
        </div>
      </div>
      <a-empty v-else-if="!loading" />
    </a-spin>
  </a-modal>
</template>
