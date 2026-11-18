<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCompareMessages } from '@/hooks/use-conversation'

const { t } = useI18n()
const visible = ref(false)
const baseMessageId = ref('')
const { loading, comparison, loadComparison, clearComparison } = useCompareMessages()

const open = (message_id: string) => {
  baseMessageId.value = message_id
  visible.value = true
}

const handleCompare = async (targetMessageId: string) => {
  await loadComparison(baseMessageId.value, targetMessageId)
}

const close = () => {
  visible.value = false
  clearComparison()
}

defineExpose({ open })
</script>

<template>
  <a-modal
    v-model:visible="visible"
    :title="t('chat.compareMessages.title')"
    :footer="false"
    @cancel="close"
  >
    <a-spin :loading="loading" class="w-full">
      <div v-if="comparison" class="flex flex-col gap-4">
        <!-- Compare details will be rendered here in next PR -->
        <pre class="text-xs bg-gray-100 p-2 rounded">{{ JSON.stringify(comparison, null, 2) }}</pre>
      </div>
      <a-empty v-else-if="!loading" />
    </a-spin>
  </a-modal>
</template>
