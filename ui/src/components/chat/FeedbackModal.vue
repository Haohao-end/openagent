<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Message } from '@arco-design/web-vue'
import { useFeedback } from '@/hooks/use-feedback'
import type { FeedbackRating, FeedbackTargetType } from '@/models/feedback'

const emit = defineEmits<{
  (e: 'submitted', feedbackId: string): void
}>()

const { t } = useI18n()
const visible = ref(false)
const appId = ref('')
const targetId = ref('')
const targetType = ref<FeedbackTargetType>('message')
const rating = ref<FeedbackRating | null>(null)
const content = ref('')

const { loading, submitFeedback, clearFeedback } = useFeedback()

const open = (app_id: string, target_id: string, initialRating?: FeedbackRating, target_type: FeedbackTargetType = 'message') => {
  appId.value = app_id
  targetId.value = target_id
  targetType.value = target_type
  rating.value = initialRating ?? null
  content.value = ''
  visible.value = true
}

const close = () => {
  visible.value = false
  clearFeedback()
}

const handleSubmit = async () => {
  if (loading.value) return
  if (!appId.value || !targetId.value) return
  if (!rating.value) {
    Message.warning(t('chat.feedback.selectRating'))
    return
  }

  const result = await submitFeedback(appId.value, {
    target_id: targetId.value,
    target_type: targetType.value,
    rating: rating.value,
    content: content.value.trim() || undefined,
  })

  if (result) {
    Message.success(t('chat.feedback.submitSuccess'))
    emit('submitted', result.id)
    close()
  }
}

defineExpose({ open, handleSubmit })
</script>

<template>
  <a-modal
    v-model:visible="visible"
    :title="t('chat.feedback.title')"
    :footer="false"
    width="480px"
    @cancel="close"
  >
    <a-spin :loading="loading" class="w-full">
      <div class="flex flex-col gap-4">
        <!-- Rating Select -->
        <div class="flex items-center justify-center gap-6 py-2">
          <button
            type="button"
            class="flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-all"
            :class="rating === 1 ? 'border-green-500 bg-green-50 text-green-700 font-medium' : 'border-gray-200 text-gray-600 hover:bg-gray-50'"
            @click="rating = 1"
          >
            <icon-thumb-up />
            <span>{{ t('chat.feedback.like') }}</span>
          </button>

          <button
            type="button"
            class="flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-all"
            :class="rating === -1 ? 'border-rose-500 bg-rose-50 text-rose-700 font-medium' : 'border-gray-200 text-gray-600 hover:bg-gray-50'"
            @click="rating = -1"
          >
            <icon-thumb-down />
            <span>{{ t('chat.feedback.dislike') }}</span>
          </button>
        </div>

        <!-- Content Input -->
        <div class="flex flex-col gap-1">
          <a-textarea
            v-model="content"
            :placeholder="t('chat.feedback.contentPlaceholder')"
            :auto-size="{ minRows: 3, maxRows: 6 }"
            :max-length="500"
            show-word-limit
          />
        </div>

        <!-- Actions -->
        <div class="flex justify-end gap-2 pt-2 border-t">
          <a-button :disabled="loading" @click="close">{{ t('common.cancel') }}</a-button>
          <a-button
            type="primary"
            :loading="loading"
            :disabled="loading"
            @click="handleSubmit"
          >
            {{ t('common.submit') }}
          </a-button>
        </div>
      </div>
    </a-spin>
  </a-modal>
</template>
