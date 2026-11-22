<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Message } from '@arco-design/web-vue'
import { useGetMessageTrace } from '@/hooks/use-conversation'
import { getErrorMessage } from '@/utils/error'

const { t } = useI18n()
const visible = ref(false)
const { loading, trace, loadMessageTrace, clearMessageTrace } = useGetMessageTrace()

const open = async (message_id: string) => {
  visible.value = true
  try {
    await loadMessageTrace(message_id)
  } catch (error) {
    Message.error(getErrorMessage(error, t('chat.messageTrace.loadFailed')))
  }
}

const close = () => {
  visible.value = false
  clearMessageTrace()
}

const isSuccessStatus = (status: string) => {
  const s = status.toLowerCase()
  return s === 'succeeded' || s === 'completed' || s === 'success'
}

const isFailedStatus = (status: string) => {
  const s = status.toLowerCase()
  return s === 'failed' || s === 'error'
}

defineExpose({ open })
</script>

<template>
  <a-modal
    v-model:visible="visible"
    :title="t('chat.messageTrace.title')"
    :footer="false"
    width="680px"
    @cancel="close"
  >
    <a-spin :loading="loading" class="w-full">
      <div v-if="trace" class="flex flex-col gap-4">
        <!-- Overview Summary -->
        <div class="grid grid-cols-4 gap-3 p-3 bg-gray-50 rounded-lg text-xs">
          <div>
            <div class="text-gray-500 mb-1">{{ t('chat.messageTrace.status') }}</div>
            <a-tag
              size="small"
              :color="isSuccessStatus(trace.status) ? 'green' : isFailedStatus(trace.status) ? 'red' : 'gray'"
            >
              {{ trace.status }}
            </a-tag>
          </div>
          <div>
            <div class="text-gray-500 mb-1">{{ t('chat.messageTrace.latency') }}</div>
            <div class="font-medium text-gray-800 text-sm">{{ trace.latency }}s</div>
          </div>
          <div>
            <div class="text-gray-500 mb-1">{{ t('chat.messageTrace.tokens') }}</div>
            <div class="font-medium text-gray-800 text-sm">{{ trace.total_token_count }}</div>
          </div>
          <div>
            <div class="text-gray-500 mb-1">{{ t('chat.messageTrace.price') }}</div>
            <div class="font-medium text-gray-800 text-sm">¥{{ trace.total_price }}</div>
          </div>
        </div>

        <!-- Spans Timeline -->
        <div class="flex flex-col gap-2">
          <div class="text-xs font-semibold text-gray-700">
            {{ t('chat.messageTrace.spans') }} ({{ trace.timeline?.length || 0 }})
          </div>

          <div
            v-if="trace.timeline && trace.timeline.length > 0"
            class="flex flex-col gap-3 max-h-[50vh] overflow-y-auto pr-1"
          >
            <div
              v-for="span in trace.timeline"
              :key="span.id"
              class="border rounded-lg p-3 bg-white flex flex-col gap-2 text-xs"
            >
              <!-- Span header -->
              <div class="flex items-center justify-between border-b pb-2">
                <div class="flex items-center gap-2">
                  <span class="font-semibold text-gray-500">#{{ span.position + 1 }}</span>
                  <a-tag size="small" color="arcoblue">{{ span.event }}</a-tag>
                  <a-tag v-if="span.tool" size="small" color="purple">{{ span.tool }}</a-tag>
                </div>
                <div class="text-gray-400 flex items-center gap-2">
                  <span>{{ span.latency }}s</span>
                  <span>{{ span.total_token_count }} tokens</span>
                </div>
              </div>

              <!-- Thought -->
              <div v-if="span.thought" class="bg-amber-50 text-amber-900 rounded p-2 text-xs">
                <div class="font-semibold text-amber-700 mb-1">{{ t('chat.messageTrace.thought') }}:</div>
                <div class="whitespace-pre-wrap">{{ span.thought }}</div>
              </div>

              <!-- Tool input -->
              <div v-if="span.tool_input && Object.keys(span.tool_input).length > 0" class="bg-gray-50 rounded p-2">
                <div class="font-semibold text-gray-600 mb-1">{{ t('chat.messageTrace.toolInput') }}:</div>
                <pre class="text-[11px] text-gray-700 overflow-x-auto">{{ JSON.stringify(span.tool_input, null, 2) }}</pre>
              </div>

              <!-- Observation -->
              <div v-if="span.observation" class="bg-emerald-50 text-emerald-900 rounded p-2 text-xs">
                <div class="font-semibold text-emerald-700 mb-1">{{ t('chat.messageTrace.observation') }}:</div>
                <div class="whitespace-pre-wrap">{{ span.observation }}</div>
              </div>
            </div>
          </div>

          <div v-else class="text-xs text-gray-400 text-center py-4">
            {{ t('chat.messageTrace.noSpans') }}
          </div>
        </div>
      </div>
      <a-empty v-else-if="!loading" />
    </a-spin>
  </a-modal>
</template>
