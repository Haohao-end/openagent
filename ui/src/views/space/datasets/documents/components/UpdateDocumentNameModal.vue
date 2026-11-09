<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { type Form, type ValidatedError, Message } from '@arco-design/web-vue'
import { useGetDocument, useUpdateDocumentName } from '@/hooks/use-dataset'
import { getErrorMessage } from '@/utils/error'

// 1.定义组件所需要使用的数据
const props = defineProps({
  visible: { type: Boolean, required: true },
  dataset_id: { type: String, required: true },
  document_id: { type: String, required: true },
  onAfterUpdate: {
    type: Function,
    required: false,
    default: () => {
      return {}
    },
  },
})
const emits = defineEmits(['update:visible'])
const { document, loading: documentLoading, loadDocument } = useGetDocument()
const { loading: updateDocumentNameLoading, handleUpdateDocumentName } = useUpdateDocumentName()
const form = ref({ name: '' })
const detailLoadFailed = ref(false)
const formRef = ref<InstanceType<typeof Form>>()
const { t } = useI18n()
let modalGeneration = 0

// 2.定义关闭模态窗函数，执行关闭模态窗并重置表单操作
const hideModal = () => {
  modalGeneration += 1
  emits('update:visible', false)
  formRef.value?.resetFields()
}

// 3.定义表单提交函数
const handleSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 3.1 判断数据校验是否成功
  if (errors || documentLoading.value || detailLoadFailed.value) return

  // 3.3 调用处理器发起请求
  const generation = modalGeneration
  await handleUpdateDocumentName(props.dataset_id, props.document_id, form.value.name)
  if (generation !== modalGeneration) return

  // 3.4 隐藏模态窗并重置表单
  hideModal()

  // 3.5 调用完成后的回调函数
  props.onAfterUpdate()
}

// 4.监听visible，当模态窗开启的时候，我们需要调用接口获取数据并填充到表单中
watch(
  () => props.visible,
  async (newValue: boolean) => {
    const generation = ++modalGeneration
    if (newValue) {
      detailLoadFailed.value = false
      try {
        await loadDocument(props.dataset_id, props.document_id)
      } catch (error: unknown) {
        if (generation !== modalGeneration || !props.visible) return
        detailLoadFailed.value = true
        Message.error(getErrorMessage(error, t('space.datasets.documents.renameModal.detailLoadFailed')))
        return
      }
      if (generation !== modalGeneration) return

      formRef.value?.resetFields()
      form.value.name = document.value.name
    }
  },
)
onBeforeUnmount(() => {
  modalGeneration += 1
})
</script>

<template>
  <a-modal
    :width="520"
    :visible="visible"
    hide-title
    :footer="false"
    modal-class="rounded-xl"
    @cancel="hideModal"
  >
    <!-- 顶部标题 -->
    <div class="flex items-center justify-between">
      <div class="text-lg font-bold text-gray-700">{{ t('space.datasets.documents.renameModal.title') }}</div>
      <a-button type="text" class="!text-gray-700" size="small" @click="hideModal">
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>
    <!-- 中间表单 -->
    <div class="pt-6">
      <a-form ref="formRef" :model="form" @submit="handleSubmit" layout="vertical">
        <a-form-item
          field="name"
          :label="t('space.datasets.documents.renameModal.nameLabel')"
          asterisk-position="end"
          :rules="[{ required: true, message: t('space.datasets.documents.renameModal.nameRequired') }]"
        >
          <a-input
            v-model="form.name"
            :placeholder="t('space.datasets.documents.renameModal.namePlaceholder')"
            show-word-limit
            :max-length="100"
          />
        </a-form-item>
        <!-- 底部按钮 -->
        <div class="flex items-center justify-between">
          <div class=""></div>
          <a-space :size="16">
            <a-button class="rounded-lg" @click="hideModal">{{ t('space.datasets.documents.renameModal.cancel') }}</a-button>
            <a-button
              :loading="updateDocumentNameLoading"
              type="primary"
              html-type="submit"
              class="rounded-lg"
            >
              {{ t('space.datasets.documents.renameModal.save') }}
            </a-button>
          </a-space>
        </div>
      </a-form>
    </div>
  </a-modal>
</template>

<style scoped></style>
