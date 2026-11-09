<script setup lang="ts">
import { useUpdateConversationName } from '@/hooks/use-conversation'
import type { Form, ValidatedError } from '@arco-design/web-vue'
import { onUnmounted, ref, watch } from 'vue'

// 1.定义组件参数
const props = defineProps({
  visible: { type: Boolean, required: true },
  conversation_id: { type: String, default: '', required: false },
  conversation_name: { type: String, default: '', required: false },
})
const emits = defineEmits(['update:visible', 'saved'])

const {
  loading: updateConversationNameLoading,
  handleUpdateConversationName,
} = useUpdateConversationName()
const formRef = ref<InstanceType<typeof Form>>()
const form = ref({ name: '' })
let saveSession = 0

// 2.定义关闭弹窗函数
const hideModal = () => {
  saveSession += 1
  emits('update:visible', false)
}

// 3.定义保存会话名称函数
const saveName = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  if (errors) return

  const requestSession = ++saveSession
  const conversationId = props.conversation_id
  const name = form.value.name
  await handleUpdateConversationName(conversationId, name)
  if (requestSession !== saveSession || !props.visible) return
  emits('saved', conversationId, name)
  emits('update:visible', false)
}

// 4.监听弹窗显示状态变化，自动回填名称
watch(
  () => [props.visible, props.conversation_id] as const,
  ([visible]) => {
    saveSession += 1
    formRef.value?.resetFields()
    if (!visible) {
      form.value.name = ''
      return
    }
    form.value.name = props.conversation_name
  },
  { flush: 'sync' },
)

onUnmounted(() => {
  saveSession += 1
})
</script>

<template>
  <a-modal
    :width="520"
    :visible="props.visible"
    hide-title
    :footer="false"
    modal-class="rounded-xl"
    @cancel="hideModal"
  >
    <div class="flex items-center justify-between">
      <div class="text-lg font-bold text-gray-700">重命名会话</div>
      <a-button type="text" class="!text-gray-700" size="small" @click="hideModal">
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>
    <div class="pt-6">
      <a-form ref="formRef" :model="form" layout="vertical" @submit="saveName">
        <a-form-item
          field="name"
          label="会话名称"
          asterisk-position="end"
          :rules="[{ required: true, message: '会话名称不能为空' }]"
        >
          <a-input v-model:model-value="form.name" placeholder="请输入新会话名称" />
        </a-form-item>
        <div class="flex items-center justify-end gap-3">
          <a-button class="rounded-lg" @click="hideModal">取消</a-button>
          <a-button
            type="primary"
            html-type="submit"
            class="rounded-lg"
            :loading="updateConversationNameLoading"
          >
            确认
          </a-button>
        </div>
      </a-form>
    </div>
  </a-modal>
</template>
