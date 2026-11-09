<script setup lang="ts">
import { Message } from '@arco-design/web-vue'
import { useGetDebugConversationSummary, useUpdateDebugConversationSummary } from '@/hooks/use-app'
import { getErrorMessage } from '@/utils/error'
import { onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

// 1.定义自定义组件所需数据
const { t } = useI18n()
const props = defineProps({
  app_id: { type: String, required: true },
  long_term_memory: {
    type: Object,
    default: () => {
      return { enable: false }
    },
    required: true,
  },
})
const { debug_conversation_summary, loadDebugConversationSummary } =
  useGetDebugConversationSummary()
const { loading, handleUpdateDebugConversationSummary } = useUpdateDebugConversationSummary()
const summaryModalVisible = ref(false)
let saveSession = 0
let loadSession = 0

watch(summaryModalVisible, () => {
  saveSession += 1
}, { flush: 'sync' })
watch(() => props.app_id, () => {
  saveSession += 1
  loadSession += 1
  summaryModalVisible.value = false
  debug_conversation_summary.value = ''
}, { flush: 'sync' })

// 2.模态窗打开处理器
const openSummaryModal = async () => {
  const requestId = ++loadSession
  const appId = props.app_id
  // 2.1 调用API获取长期记忆
  await loadDebugConversationSummary(appId, () => requestId === loadSession && props.app_id === appId)
  if (requestId !== loadSession || props.app_id !== appId) return

  // 2.2 开启模态窗
  summaryModalVisible.value = true
}

const saveSummary = async () => {
  const requestSession = ++saveSession
  const appId = props.app_id
  const summary = debug_conversation_summary.value
  try {
    await handleUpdateDebugConversationSummary(appId, summary)
  } catch (error: unknown) {
    if (requestSession === saveSession && summaryModalVisible.value && props.app_id === appId) {
      Message.error(getErrorMessage(error, t('appStudio.debug.summarySaveFailed')))
    }
    return
  }
  if (requestSession === saveSession && summaryModalVisible.value && props.app_id === appId) {
    summaryModalVisible.value = false
  }
}

onUnmounted(() => {
  saveSession += 1
  loadSession += 1
})
</script>

<template>
  <div class="">
    <!-- 预览与调试头组件 -->
    <div class="flex items-center justify-between border-b h-[64px] px-4">
      <div class="text-lg text-gray-700">{{ t('appStudio.debug.title') }}</div>
      <a-button
        :disabled="!props.long_term_memory?.enable"
        size="mini"
        type="text"
        class="rounded-lg px-1 !text-blue-700"
        @click="openSummaryModal"
      >
        <template #icon>
          <icon-save />
        </template>
        {{ t('appStudio.debug.longTermMemory') }}
      </a-button>
    </div>
    <!-- 长期记忆模态窗 -->
    <a-modal
      :width="520"
      v-model:visible="summaryModalVisible"
      hide-title
      :footer="false"
      modal-class="rounded-xl"
    >
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between">
        <div class="text-lg font-bold text-gray-700">
          {{ t('appStudio.debug.longTermMemory') }}
        </div>
        <a-button
          type="text"
          class="!text-gray-700"
          size="small"
          @click="summaryModalVisible = false"
        >
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 底部表单 -->
      <div class="pt-6">
        <a-textarea
          v-model:model-value="debug_conversation_summary"
          :placeholder="t('appStudio.debug.longTermMemoryPlaceholder')"
          show-word-limit
          :max-length="2000"
          :auto-size="{ minRows: 8, maxRows: 8 }"
        />
        <!-- 底部按钮 -->
        <div class="flex items-center justify-between">
          <div class=""></div>
          <a-space :size="16">
            <a-button class="rounded-lg" @click="summaryModalVisible = false">
              {{ t('common.actions.cancel') }}
            </a-button>
            <a-button
              :loading="loading"
              type="primary"
              class="rounded-lg"
              @click="saveSummary"
            >
              {{ t('common.actions.save') }}
            </a-button>
          </a-space>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<style scoped></style>
