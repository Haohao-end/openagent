<script setup lang="ts">
import { ref, watch } from 'vue'
import { type Form, type ValidatedError, Message } from '@arco-design/web-vue'
import { useCreateApp, useGetApp, useUpdateApp, useRegenerateIcon, useGenerateIconPreview } from '@/hooks/use-app'
import { useUploadImage } from '@/hooks/use-upload-file'
import IconUploadGenerator from '@/components/IconUploadGenerator.vue'
import { getErrorMessage } from '@/utils/error'

// 1.定义自定义组件所需数据
const props = defineProps({
  app_id: { type: String, default: '', required: false },
  visible: { type: Boolean, required: true },
  callback: { type: Function, required: false },
})
const emits = defineEmits(['update:visible', 'update:app_id'])
const { loading: createAppLoading, handleCreateApp } = useCreateApp()
const { loading: updateAppLoading, handleUpdateApp } = useUpdateApp()
const { app, loadApp } = useGetApp()
const { image_url, handleUploadImage } = useUploadImage()
const { loading: regenerateIconLoading, handleRegenerateIcon } = useRegenerateIcon()
const { loading: generateIconPreviewLoading, handleGenerateIconPreview } = useGenerateIconPreview()
type IconFileItem = { uid: string; name: string; url: string }
type AppForm = {
  fileList: IconFileItem[]
  icon: string
  name: string
  description: string
}
const defaultForm: AppForm = {
  fileList: [],
  icon: '',
  name: '',
  description: '',
}
const form = ref<AppForm>({ ...defaultForm })
const formRef = ref<InstanceType<typeof Form>>()

// 2.定义隐藏模态窗函数
const hideModal = () => emits('update:visible', false)

// 2.5 定义上传图标处理器
const handleUploadIcon = async (file: File) => {
  try {
    await handleUploadImage(file)
    form.value.icon = image_url.value
    form.value.fileList = [{ uid: '1', name: '应用图标', url: image_url.value }]
    Message.success('图标上传成功')
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '图标上传失败'))
    throw error
  }
}

// 2.6 定义生成图标处理器
const handleGenerateIcon = async () => {
  if (!form.value.name || form.value.name.trim() === '') {
    Message.warning('请先输入应用名称')
    return
  }

  try {
    // 如果是更新模式，调用regenerate API
    if (props.app_id) {
      const iconUrl = await handleRegenerateIcon(props.app_id)
      if (iconUrl) {
        form.value.icon = iconUrl
        form.value.fileList = [{ uid: '1', name: '应用图标', url: iconUrl }]
        Message.success('图标生成成功')
      }
    } else {
      const iconUrl = await handleGenerateIconPreview(form.value.name, form.value.description)
      if (iconUrl) {
        form.value.icon = iconUrl
        form.value.fileList = [{ uid: '1', name: '应用图标', url: iconUrl }]
        Message.success('图标生成成功')
      }
    }
  } catch {
    // 错误已在 hook 内统一处理并提示
  }
}

// 3.定义表单提交函数
const saveApp = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 3.1 判断表单是否出错
  if (errors) return

  // 3.2 检测是保存还是新增，调用不同的API接口
  if (props.app_id) {
    await handleUpdateApp(props.app_id, form.value)
  } else {
    await handleCreateApp(form.value)
  }

  // 3.3 完成保存操作，隐藏模态窗并调用回调函数
  emits('update:visible', false)
  props.callback && props.callback()
}

// 4.监听模态窗显示状态变化
watch(
  () => props.visible,
  async (newValue) => {
    // 4.1 清除表单校验信息
    formRef.value?.resetFields()

    // 4.2 判断弹窗是打开还是关闭
    if (newValue) {
      // 4.3 开启弹窗，需要检测下是更新还是创建操作
      if (props.app_id) {
        // 4.4 调用接口获取文档片段详情
        await loadApp(props.app_id)

        // 4.5 更新表单数据
        form.value = {
          fileList: [{ uid: '1', name: '应用图标', url: app.value.icon }],
          icon: app.value.icon,
          name: app.value.name,
          description: app.value.description,
        }
      }
    } else {
      // 4.6 关闭弹窗，需要清空表单数据
      form.value = defaultForm
      formRef.value?.resetFields()
      emits('update:app_id', '')
    }
  },
)
</script>

<template>
  <a-modal
    :width="560"
    :visible="props.visible"
    hide-title
    :footer="false"
    modal-class="rounded-xl"
    @cancel="hideModal"
  >
    <!-- 顶部标题 -->
    <div class="flex items-center justify-between mb-6">
      <div class="text-xl font-bold text-gray-800">
        {{ props.app_id === '' ? '创建 AI 应用' : '编辑 AI 应用' }}
      </div>
      <a-button type="text" class="!text-gray-500 hover:!text-gray-700" size="small" @click="hideModal">
        <template #icon>
          <icon-close :size="20" />
        </template>
      </a-button>
    </div>
    <!-- 中间表单 -->
    <div>
      <a-form ref="formRef" :model="form" layout="vertical" @submit="saveApp">
        <a-form-item field="icon" hide-label>
          <IconUploadGenerator
            :name="form.name"
            :description="form.description"
            :icon="form.icon"
            :file-list="form.fileList"
            :loading="regenerateIconLoading || generateIconPreviewLoading"
            placeholder="应用"
            :on-upload="handleUploadIcon"
            :on-generate="handleGenerateIcon"
            @update:icon="(val) => (form.icon = val)"
            @update:fileList="(val) => (form.fileList = val)"
          />
        </a-form-item>
        <a-form-item
          field="name"
          label="应用名称"
          asterisk-position="end"
          :rules="[{ required: true, message: '应用名称不能为空' }]"
        >
          <a-input
            v-model:model-value="form.name"
            placeholder="请输入应用名称"
            size="large"
            class="rounded-lg"
          />
        </a-form-item>
        <a-form-item field="description" label="应用描述">
          <a-textarea
            v-model:model-value="form.description"
            :auto-size="{ minRows: 6, maxRows: 8 }"
            :max-length="800"
            show-word-limit
            placeholder="请输入关于该应用的描述信息"
            class="rounded-lg"
          />
        </a-form-item>
        <!-- 底部按钮 -->
        <div class="flex items-center justify-end gap-3 mt-6">
          <a-button size="large" class="rounded-lg px-6" @click="hideModal">取消</a-button>
          <a-button
            :loading="createAppLoading || updateAppLoading"
            type="primary"
            html-type="submit"
            size="large"
            class="rounded-lg px-6"
          >
            保存
          </a-button>
        </div>
      </a-form>
    </div>
  </a-modal>
</template>

<style scoped></style>
