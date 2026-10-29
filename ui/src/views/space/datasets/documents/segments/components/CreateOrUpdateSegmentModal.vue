<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { type Form, type ValidatedError } from '@arco-design/web-vue'
import { useCreateSegment, useGetSegment, useUpdateSegment } from '@/hooks/use-dataset'
import type { CreateSegmentRequest, UpdateSegmentRequest } from '@/models/dataset'

// 1.定义自定义组件所需数据
const props = defineProps({
  dataset_id: { type: String, required: false },
  document_id: { type: String, required: false },
  segment_id: { type: String, required: false },
  visible: { type: Boolean, required: true },
  callback: { type: Function, required: false },
})
const emits = defineEmits(['update:visible'])
const { loading: createSegmentLoading, handleCreateSegment } = useCreateSegment()
const { loading: updateSegmentLoading, handleUpdateSegment } = useUpdateSegment()
const { loadSegment } = useGetSegment()
const { t } = useI18n()
const createDefaultForm = (): { content: string; keywords: string[] } => ({ content: '', keywords: [] })
const form = ref(createDefaultForm())
const formRef = ref<InstanceType<typeof Form>>()
const isUpdateOperation = computed(() => props.segment_id && props.segment_id !== '')

// 2.定义隐藏模态窗函数
const hideModal = () => emits('update:visible', false)

// 3.定义表单提交函数
const saveSegment = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 3.1 判断表单是否出错
  if (errors) return

  // 3.2 检测是保存还是新增，调用不同的API接口
  if (isUpdateOperation.value) {
    // 3.3 更新文档片段信息
    await handleUpdateSegment(
      props.dataset_id as string,
      props.document_id as string,
      props.segment_id as string,
      form.value as UpdateSegmentRequest,
    )
  } else {
    // 3.4 新增文档片段信息
    await handleCreateSegment(
      props.dataset_id as string,
      props.document_id as string,
      form.value as CreateSegmentRequest,
    )
  }

  // 3.5 完成保存操作，隐藏模态窗并调用回调函数
  emits('update:visible', false)
  props.callback && props.callback()
}

// 4.监听模态窗显示状态变化
let latestLoadRequest = 0
watch(
  () => props.visible,
  async (newValue) => {
    const requestId = ++latestLoadRequest
    // 4.1 清除表单校验信息
    formRef.value?.resetFields()

    // 4.2 判断弹窗是打开还是关闭
    if (newValue) {
      // 4.3 开启弹窗，需要检测下是更新还是创建操作
      if (isUpdateOperation.value) {
        // 4.4 调用接口获取文档片段详情
        const segmentId = props.segment_id as string
        const loadedSegment = await loadSegment(
          props.dataset_id as string,
          props.document_id as string,
          segmentId,
        )
        if (
          requestId !== latestLoadRequest ||
          !props.visible ||
          props.segment_id !== segmentId ||
          !loadedSegment
        ) return

        // 4.5 更新表单数据
        form.value.content = loadedSegment.content
        form.value.keywords = loadedSegment.keywords
      }
    } else {
      // 4.6 关闭弹窗，需要清空表单数据
      formRef.value?.resetFields()
      form.value = createDefaultForm()
    }
  },
)
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
    <!-- 顶部标题 -->
    <div class="flex items-center justify-between">
      <div class="text-lg font-bold text-gray-700">
        {{ isUpdateOperation ? t('space.datasets.documents.segmentsModal.updateTitle') : t('space.datasets.documents.segmentsModal.createTitle') }}
      </div>
      <a-button type="text" class="!text-gray-700" size="small" @click="hideModal">
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>
    <!-- 中间表单 -->
    <div class="pt-6">
      <a-form ref="formRef" :model="form" layout="vertical" @submit="saveSegment">
        <a-form-item
          field="content"
          :label="t('space.datasets.documents.segmentsModal.contentLabel')"
          asterisk-position="end"
          :rules="[{ required: true, message: t('space.datasets.documents.segmentsModal.contentRequired') }]"
        >
          <a-textarea
            v-model:model-value="form.content"
            :auto-size="{ minRows: 8, maxRows: 8 }"
            :placeholder="t('space.datasets.documents.segmentsModal.contentPlaceholder')"
          />
        </a-form-item>
        <a-form-item field="keywords" :label="t('space.datasets.documents.segmentsModal.keywordsLabel')">
          <a-input-tag
            v-model:model-value="form.keywords"
            :max-tag-count="10"
            :placeholder="t('space.datasets.documents.segmentsModal.keywordsPlaceholder')"
          />
        </a-form-item>
        <!-- 底部按钮 -->
        <div class="flex items-center justify-between">
          <div class=""></div>
          <a-space :size="16">
            <a-button class="rounded-lg" @click="hideModal">{{ t('space.datasets.documents.segmentsModal.cancel') }}</a-button>
            <a-button
              :loading="updateSegmentLoading || createSegmentLoading"
              type="primary"
              html-type="submit"
              class="rounded-lg"
            >
              {{ t('space.datasets.documents.segmentsModal.save') }}
            </a-button>
          </a-space>
        </div>
      </a-form>
    </div>
  </a-modal>
</template>

<style scoped></style>
