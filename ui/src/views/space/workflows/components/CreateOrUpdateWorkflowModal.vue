<script setup lang="ts">
import { ref, watch } from 'vue'
import { type Form, type ValidatedError, Message } from '@arco-design/web-vue'
import {
  useCreateWorkflow,
  useGenerateIconPreview,
  useGetWorkflow,
  useRegenerateIcon,
  useUpdateWorkflow,
} from '@/hooks/use-workflow'
import { useUploadImage } from '@/hooks/use-upload-file'
import IconUploadGenerator from '@/components/IconUploadGenerator.vue'
import { getErrorMessage } from '@/utils/error'

// 1.定义自定义组件所需数据
const props = defineProps({
  workflow_id: { type: String, default: '', required: false },
  visible: { type: Boolean, required: true },
  callback: { type: Function, required: false },
})
const emits = defineEmits(['update:visible', 'update:workflow_id'])
const { loading: createWorkflowLoading, handleCreateWorkflow } = useCreateWorkflow()
const { loading: updateWorkflowLoading, handleUpdateWorkflow } = useUpdateWorkflow()
const { workflow, loadWorkflow } = useGetWorkflow()
const { image_url, handleUploadImage } = useUploadImage()
const { loading: regenerateIconLoading, handleRegenerateIcon } = useRegenerateIcon()
const { loading: generateIconPreviewLoading, handleGenerateIconPreview } = useGenerateIconPreview()
type IconFileItem = { uid: string; name: string; url: string }
const defaultForm = {
  fileList: [] as IconFileItem[],
  icon: '',
  name: '',
  tool_call_name: '',
  description: '',
}
const form = ref({ ...defaultForm })
const formRef = ref<InstanceType<typeof Form>>()

// 2.定义上传图标处理器
const handleUploadIcon = async (file: File) => {
  await handleUploadImage(file)
  form.value.icon = image_url.value
  form.value.fileList = [{ uid: '1', name: '工作流图标', url: image_url.value }]
  Message.success('图标上传成功')
}

// 3.定义生成图标处理器
const handleGenerateIcon = async () => {
  if (!form.value.name || form.value.name.trim() === '') {
    Message.warning('请先输入工作流名称')
    return
  }

  try {
    // 更新模式：调用 regenerateIcon
    if (props.workflow_id) {
      const iconUrl = await handleRegenerateIcon(props.workflow_id)
      if (iconUrl) {
        form.value.icon = iconUrl
        form.value.fileList = [{ uid: '1', name: '工作流图标', url: iconUrl }]
        Message.success('图标生成成功')
      }
    }
    // 创建模式：调用 generateIconPreview
    else {
      const iconUrl = await handleGenerateIconPreview(form.value.name, form.value.description)
      if (iconUrl) {
        form.value.icon = iconUrl
        form.value.fileList = [{ uid: '1', name: '工作流图标', url: iconUrl }]
        Message.success('图标生成成功')
      }
    }
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '图标生成失败'))
  }
}

// 4.定义隐藏模态窗函数
const hideModal = () => emits('update:visible', false)

// 5.定义表单提交函数
const saveWorkflow = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 3.1 判断表单是否出错
  if (errors) return

  // 3.2 检测是保存还是新增，调用不同的API接口
  if (props.workflow_id) {
    await handleUpdateWorkflow(props.workflow_id, form.value)
  } else {
    await handleCreateWorkflow(form.value)
  }

  // 3.3 完成保存操作，隐藏模态窗并调用回调函数
  emits('update:visible', false)
  props.callback && props.callback()
}

// 6.监听模态窗显示状态变化
watch(
  () => props.visible,
  async (newValue) => {
    // 4.1 清除表单校验信息
    formRef.value?.resetFields()

    // 4.2 判断弹窗是打开还是关闭
    if (newValue) {
      // 4.3 开启弹窗，需要检测下是更新还是创建操作
      if (props.workflow_id) {
        // 4.4 调用接口获取工作流详情
        await loadWorkflow(props.workflow_id)

        // 4.5 更新表单数据
        form.value = {
          fileList: [{ uid: '1', name: '应用图标', url: String(workflow.value?.icon) }],
          icon: String(workflow.value?.icon),
          name: String(workflow.value?.name),
          tool_call_name: String(workflow.value?.tool_call_name),
          description: String(workflow.value?.description),
        }
      }
    } else {
      // 4.6 关闭弹窗，需要清空表单数据
      form.value = defaultForm
      formRef.value?.resetFields()
      emits('update:workflow_id', '')
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
        {{ props.workflow_id === '' ? '创建工作流' : '编辑工作流' }}
      </div>
      <a-button type="text" class="!text-gray-700" size="small" @click="hideModal">
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>
    <!-- 中间表单 -->
    <div class="pt-6">
      <a-form ref="formRef" :model="form" layout="vertical" @submit="saveWorkflow">
        <a-form-item
          field="fileList"
          hide-label
          :rules="[{ required: true, message: '工作流图标不能为空' }]"
        >
          <IconUploadGenerator
            :name="form.name"
            :description="form.description"
            :icon="form.icon"
            :file-list="form.fileList"
            :loading="regenerateIconLoading || generateIconPreviewLoading"
            placeholder="工作流"
            :on-upload="handleUploadIcon"
            :on-generate="handleGenerateIcon"
            @update:icon="(val) => (form.icon = val)"
            @update:fileList="(val) => (form.fileList = val)"
          />
        </a-form-item>
        <a-form-item
          field="name"
          label="工作流名称"
          asterisk-position="end"
          :rules="[{ required: true, message: '工作流名称不能为空' }]"
        >
          <a-input
            show-word-limit
            :max-length="50"
            v-model:model-value="form.name"
            placeholder="请输入工作流名称"
          />
        </a-form-item>
        <a-form-item
          field="tool_call_name"
          label="英文名称"
          asterisk-position="end"
          :rules="[{ required: true, message: '英文名称不能为空' }]"
        >
          <a-input
            show-word-limit
            :max-length="50"
            v-model:model-value="form.tool_call_name"
            placeholder="英文名称将用于被大模型识别及调用"
          />
        </a-form-item>
        <a-form-item
          field="description"
          label="工作流描述"
          asterisk-position="end"
          :rules="[{ required: true, message: '工作流描述不能为空' }]"
        >
          <a-textarea
            v-model:model-value="form.description"
            :auto-size="{ minRows: 8, maxRows: 8 }"
            :max-length="1024"
            show-word-limit
            placeholder="请输入关于该工作流的描述信息，以便LLM能准确识别工作流的用途。"
          />
        </a-form-item>
        <!-- 底部按钮 -->
        <div class="flex items-center justify-between">
          <div class=""></div>
          <a-space :size="16">
            <a-button class="rounded-lg" @click="hideModal">取消</a-button>
            <a-button
              :loading="createWorkflowLoading || updateWorkflowLoading"
              type="primary"
              html-type="submit"
              class="rounded-lg"
            >
              保存
            </a-button>
          </a-space>
        </div>
      </a-form>
    </div>
  </a-modal>
</template>

<style scoped></style>
