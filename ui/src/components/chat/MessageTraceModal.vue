<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useGetMessageTrace } from '@/hooks/use-conversation'

const { t } = useI18n()
const visible = ref(false)
const { loading, trace, loadMessageTrace, clearMessageTrace } = useGetMessageTrace()

const open = async (message_id: string) => {
  visible.value = true
  await loadMessageTrace(message_id)
}

const close = () => {
  visible.value = false
  clearMessageTrace()
}

defineExpose({ open })
</script>

<template>
  <a-modal
    v-model:visible="visible"
    :title="t('chat.messageTrace.title')"
    :footer="false"
    @cancel="close"
  >
    <a-spin :loading="loading" class="w-full">
      <div v-if="trace" class="flex flex-col gap-4">
        <div class="text-sm text-gray-700">
          <span class="font-bold">{{ t('chat.messageTrace.status') }}:</span>
          {{ trace.status }}
        </div>
        <!-- Add trace details rendering here -->
        <pre class="text-xs bg-gray-100 p-2 rounded">{{ JSON.stringify(trace, null, 2) }}</pre>
      </div>
      <a-empty v-else-if="!loading" />
    </a-spin>
  </a-modal>
</template>
