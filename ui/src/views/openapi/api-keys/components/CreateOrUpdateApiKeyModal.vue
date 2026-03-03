<script setup lang="ts">
import { ref, watch } from 'vue'
import { type ValidatedError, Message, Modal } from '@arco-design/web-vue'
import { useCreateApiKey, useUpdateApiKey } from '@/hooks/use-api-key'

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

// 2.定义隐藏模态窗函数
const hideModal = () => {
  emits('update:visible', false)
}

// 3.定义表单提交函数
const saveApiKey = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 3.1 判断表单是否出错
  if (errors) return

  // 3.2 检测是新增还是更新，执行不同的操作
  if (props.api_key_id) {
    // 3.3 执行更新操作
    await handleUpdateApiKey(props.api_key_id, {
      is_active: Boolean(form.value?.is_active),
      remark: String(form.value?.remark),
    })
  } else {
    // 3.4 执行新增操作
    const createdApiKey = await handleCreateApiKey({
      is_active: Boolean(form.value?.is_active),
      remark: String(form.value?.remark),
    })
    if (createdApiKey) {
      Modal.info({
        title: 'API 密钥（仅显示一次）',
        content: createdApiKey,
        okText: '我已保存',
      })
      try {
        await navigator.clipboard.writeText(createdApiKey)
        Message.success('API 密钥已复制到剪贴板')
      } catch {
        Message.warning('复制失败，请手动保存上方密钥')
      }
    }
  }

  // 3.5 隐藏模态窗
  hideModal()
  props.callback && props.callback()
}

// 4.监听模态窗的显示or隐藏状态
watch(
  () => props.visible,
  (newValue) => {
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
)
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
          <div class="text-lg font-bold text-gray-900">{{ api_key_id ? '编辑' : '创建' }}密钥</div>
          <div class="text-sm text-gray-500 mt-0.5">{{ api_key_id ? '更新密钥配置信息' : '创建新的 API 访问密钥' }}</div>
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
          <div class="text-sm font-semibold text-gray-700 mb-2">密钥状态</div>
        </template>
        <div class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
          <a-switch v-model:model-value="form.is_active" />
          <div class="flex-1">
            <div class="text-sm font-medium text-gray-900">
              {{ form.is_active ? '启用' : '禁用' }}
            </div>
            <div class="text-xs text-gray-500 mt-0.5">
              {{ form.is_active ? '密钥可以正常使用' : '密钥将无法访问 API' }}
            </div>
          </div>
        </div>
      </a-form-item>

      <a-form-item field="remark" class="mb-5">
        <template #label>
          <div class="text-sm font-semibold text-gray-700 mb-2">密钥备注</div>
        </template>
        <a-textarea
          v-model:model-value="form.remark"
          :max-length="100"
          show-word-limit
          placeholder="请输入密钥备注信息,例如:生产环境密钥、测试环境密钥等"
          :auto-size="{ minRows: 3, maxRows: 6 }"
          class="!rounded-lg"
        />
      </a-form-item>

      <!-- 提示 -->
      <div v-if="!api_key_id" class="mb-5 p-3 bg-amber-50 border border-amber-200 rounded-lg">
        <div class="flex items-start gap-2">
          <icon-info-circle class="text-amber-600 text-base flex-shrink-0 mt-0.5" />
          <div class="flex-1 text-sm text-amber-900">
            密钥创建后将只显示一次,请妥善保管。如果遗失,您需要重新创建新的密钥。
          </div>
        </div>
      </div>

      <!-- 按钮 -->
      <div class="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
        <a-button
          class="!rounded-lg"
          @click="() => emits('update:visible', false)"
        >
          取消
        </a-button>
        <a-button
          :loading="updateApiKeyLoading || createApiKeyLoading"
          type="primary"
          html-type="submit"
          class="!rounded-lg !bg-gray-900 hover:!bg-gray-800"
        >
          {{ api_key_id ? '保存' : '创建' }}
        </a-button>
      </div>
    </a-form>
  </a-modal>
</template>

<style scoped></style>
