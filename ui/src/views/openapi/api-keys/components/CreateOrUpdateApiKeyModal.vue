<script setup lang="ts">
import { h, onUnmounted, ref, resolveComponent, watch } from 'vue'
import { type ValidatedError, Message, Modal } from '@arco-design/web-vue'
import { useCreateApiKey, useUpdateApiKey } from '@/hooks/use-api-key'
import { copyTextToClipboard } from '@/utils/clipboard'
import { useI18n } from 'vue-i18n'

// 1.定义自定义组件所需数据
const props = defineProps({
  visible: { type: Boolean, default: false, required: true },
  api_key_id: { type: String, default: '', required: true },
  is_active: { type: Boolean, default: false, required: true },
  remark: { type: String, default: '', required: true },
  callback: { type: Function, required: false },
})
const emits = defineEmits([
  'update:visible',
  'update:api_key_id',
  'update:is_active',
  'update:remark',
])
type ApiKeyForm = {
  is_active: boolean
  remark: string
}
const form = ref<ApiKeyForm>({
  is_active: false,
  remark: '',
})
const formRef = ref(null)
const { loading: updateApiKeyLoading, handleUpdateApiKey } = useUpdateApiKey()
const { loading: createApiKeyLoading, handleCreateApiKey } = useCreateApiKey()
const IconCopy = resolveComponent('icon-copy')
const { t } = useI18n()

// 2.定义隐藏模态窗函数
let modalSession = 0

const hideModal = () => {
  modalSession += 1
  emits('update:visible', false)
}

// 3.定义表单提交函数
const saveApiKey = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 3.1 判断表单是否出错
  if (errors) return
  const requestSession = ++modalSession
  const apiKeyId = props.api_key_id
  const callback = props.callback

  // 3.2 检测是新增还是更新，执行不同的操作
  if (apiKeyId) {
    // 3.3 执行更新操作
    await handleUpdateApiKey(apiKeyId, {
      is_active: Boolean(form.value?.is_active),
      remark: String(form.value?.remark),
    })
  } else {
    // 3.4 执行新增操作
    const createdApiKey = await handleCreateApiKey({
      is_active: Boolean(form.value?.is_active),
      remark: String(form.value?.remark),
    })
    if (createdApiKey && requestSession === modalSession && props.visible) {
      Modal.info({
        title: t('openapi.apiKeys.showOnceTitle'),
        width: 860,
        modalClass: 'api-key-once-modal',
        bodyStyle: {
          paddingTop: '12px',
        },
        content: () =>
          h(
            'div',
            { class: 'api-key-once-content' },
            [
              h('div', { class: 'flex items-center justify-between gap-4' }, [
                h('p', { class: 'api-key-once-desc' }, t('openapi.apiKeys.showOnceDescription')),
                h(
                  'button',
                  {
                    class: 'md-code-copy-btn inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3.5 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100',
                    type: 'button',
                    onClick: async () => {
                      try {
                        await copyTextToClipboard(createdApiKey)
                        Message.success(t('openapi.apiKeys.copiedSuccess'))
                      } catch {
                        Message.warning(t('openapi.apiKeys.copyFailed'))
                      }
                    },
                  },
                  [
                    h(IconCopy, { class: 'text-sm' }),
                    h('span', t('common.actions.copy')),
                  ],
                ),
              ]),
              h('div', { class: 'api-key-once-code' }, createdApiKey),
            ],
          ),
        okText: t('openapi.apiKeys.showOnceSaved'),
      })
    }
  }

  if (requestSession !== modalSession || !props.visible) return

  // 3.5 隐藏模态窗
  hideModal()
  callback && callback()
}

// 4.监听模态窗的显示or隐藏状态
watch(
  () => [props.visible, props.api_key_id] as const,
  ([newValue]) => {
    modalSession += 1
    if (newValue) {
      // 4.1 显示模态窗的时候，将对应的值赋值给表单
      form.value = {
        is_active: props.is_active,
        remark: props.remark,
      }
    } else {
      // 4.2 隐藏模态窗的时候，将值清空
      emits('update:api_key_id', '')
      emits('update:is_active', false)
      emits('update:remark', '')
    }
  },
  { flush: 'sync' },
)

onUnmounted(() => {
  modalSession += 1
})
</script>

<template>
  <a-modal
    :visible="props.visible"
    @update:visible="(value) => emits('update:visible', value)"
    hide-title
    :footer="false"
    :width="520"
  >
    <!-- 顶部标题 -->
    <div class="flex items-center justify-between mb-6 pb-4 border-b border-gray-200">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-gray-900 rounded-lg flex items-center justify-center">
          <icon-safe class="text-white text-lg" />
        </div>
        <div>
          <div class="text-lg font-bold text-gray-900">{{ api_key_id ? t('openapi.apiKeys.editTitle') : t('openapi.apiKeys.createTitle') }}</div>
          <div class="text-sm text-gray-500 mt-0.5">{{ api_key_id ? t('openapi.apiKeys.updateDescription') : t('openapi.apiKeys.createDescription') }}</div>
        </div>
      </div>
      <a-button
        type="text"
        class="!text-gray-400 hover:!text-gray-600"
        @click="() => emits('update:visible', false)"
      >
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>

    <!-- 表单 -->
    <a-form ref="formRef" :model="form" layout="vertical" @submit="saveApiKey">
      <a-form-item field="is_active" class="mb-5">
        <template #label>
          <div class="text-sm font-semibold text-gray-700 mb-2">{{ t('openapi.apiKeys.statusLabel') }}</div>
        </template>
        <div class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
          <a-switch v-model:model-value="form.is_active" />
          <div class="flex-1">
            <div class="text-sm font-medium text-gray-900">
              {{ form.is_active ? t('openapi.apiKeys.enabled') : t('openapi.apiKeys.disabled') }}
            </div>
            <div class="text-xs text-gray-500 mt-0.5">
              {{ form.is_active ? t('openapi.apiKeys.statusEnabledDesc') : t('openapi.apiKeys.statusDisabledDesc') }}
            </div>
          </div>
        </div>
      </a-form-item>

      <a-form-item field="remark" class="mb-5">
        <template #label>
          <div class="text-sm font-semibold text-gray-700 mb-2">{{ t('openapi.apiKeys.remarkLabel') }}</div>
        </template>
        <a-textarea
          v-model:model-value="form.remark"
          :max-length="100"
          show-word-limit
          :placeholder="t('openapi.apiKeys.remarkPlaceholder')"
          :auto-size="{ minRows: 3, maxRows: 6 }"
          class="!rounded-lg"
        />
      </a-form-item>

      <!-- 提示 -->
      <div v-if="!api_key_id" class="mb-5 p-3 bg-amber-50 border border-amber-200 rounded-lg">
        <div class="flex items-start gap-2">
          <icon-info-circle class="text-amber-600 text-base flex-shrink-0 mt-0.5" />
          <div class="flex-1 text-sm text-amber-900">
            {{ t('openapi.apiKeys.noteDescription') }}
          </div>
        </div>
      </div>

      <!-- 按钮 -->
      <div class="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
        <a-button
          class="!rounded-lg"
          @click="() => emits('update:visible', false)"
        >
          {{ t('common.actions.cancel') }}
        </a-button>
        <a-button
          :loading="updateApiKeyLoading || createApiKeyLoading"
          type="primary"
          html-type="submit"
          class="!rounded-lg !bg-gray-900 hover:!bg-gray-800"
        >
          {{ api_key_id ? t('common.actions.save') : t('openapi.apiKeys.createButton') }}
        </a-button>
      </div>
    </a-form>
  </a-modal>
</template>

<style scoped>
:global(.api-key-once-modal) {
  max-width: calc(100vw - 32px);
}

.api-key-once-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.api-key-once-desc {
  margin: 0;
  color: rgb(75 85 99);
  font-size: 14px;
  line-height: 1.6;
}

.api-key-once-code {
  padding: 18px 20px;
  border-radius: 12px;
  border: 1px solid rgb(209 213 219);
  background: rgb(249 250 251);
  color: rgb(17 24 39);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 15px;
  line-height: 1.8;
  word-break: break-all;
  white-space: pre-wrap;
  max-height: 280px;
  overflow: auto;
  user-select: all;
}
</style>
