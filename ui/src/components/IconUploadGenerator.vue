<script setup lang="ts">
import { ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'

// 定义组件props
const props = defineProps({
  name: { type: String, required: true },
  description: { type: String, default: '' },
  icon: { type: String, default: '' },
  fileList: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  placeholder: { type: String, default: '应用' },
  onUpload: { type: Function, required: true },
  onGenerate: { type: Function, required: true },
})

const emits = defineEmits(['update:icon', 'update:fileList'])

// 本地状态
const localFileList = ref(props.fileList)
const localIcon = ref(props.icon)
const isGenerating = ref(false)

// 监听props变化
watch(
  () => props.fileList,
  (newValue) => {
    localFileList.value = newValue
  },
)

watch(
  () => props.icon,
  (newValue) => {
    localIcon.value = newValue
  },
)

watch(
  () => props.loading,
  (newValue) => {
    isGenerating.value = newValue
  },
)

// 处理上传
const handleCustomRequest = async (option: any) => {
  const { fileItem, onSuccess, onError } = option
  try {
    // 上传前清空旧文件列表（确保只保留最新上传的图标）
    localFileList.value = []
    emits('update:fileList', [])

    await props.onUpload(fileItem.file)
    onSuccess()
  } catch (error: unknown) {
    onError(error as Error)
  }
}

// 处理删除
const handleBeforeRemove = async () => {
  localIcon.value = ''
  localFileList.value = []
  emits('update:icon', '')
  emits('update:fileList', [])
  return true
}

// 处理生成
const handleGenerate = async () => {
  if (!props.name || props.name.trim() === '') {
    Message.warning(`请先输入${props.placeholder}名称`)
    return
  }

  isGenerating.value = true
  try {
    await props.onGenerate()
  } catch {
    Message.error('生成图标失败，请稍后重试')
  } finally {
    isGenerating.value = false
  }
}
</script>

<template>
  <!-- 使用 Arco Space 组件实现完全居中 -->
  <a-space direction="vertical" :size="24" class="w-full bg-gradient-to-br from-gray-50 to-gray-100 rounded-2xl p-8 border border-gray-200">
    <!-- 图标预览区域 - 当有图标时显示 -->
    <div v-if="localFileList.length > 0" class="flex justify-center items-center w-full">
      <div class="relative">
        <a-image
          :src="localIcon"
          width="140"
          height="140"
          class="rounded-2xl border-2 border-gray-200"
          preview
        />
        <a-button
          size="small"
          type="text"
          class="absolute top-1 right-1 !text-white bg-black/50 hover:bg-black/70 rounded-lg"
          @click="handleBeforeRemove"
        >
          <template #icon>
            <icon-delete />
          </template>
        </a-button>
      </div>
    </div>

    <!-- 上传/替换按钮 - 根据是否有图标显示不同文字 -->
    <div class="flex justify-center w-full">
      <a-upload
        accept="image/png, image/jpeg, image/jpg, image/webp"
        :custom-request="handleCustomRequest"
        :show-file-list="false"
      >
        <template #upload-button>
          <a-button type="outline" size="large" class="rounded-lg px-8">
            <template #icon>
              <icon-upload />
            </template>
            {{ localFileList.length > 0 ? '替换图标' : '上传图标' }}
          </a-button>
        </template>
      </a-upload>
    </div>

    <!-- AI 生成按钮 - 完全居中 -->
    <div class="flex justify-center w-full">
      <a-button
        :loading="isGenerating"
        type="primary"
        size="large"
        class="rounded-lg px-8"
        @click="handleGenerate"
      >
        <template #icon>
          <icon-robot v-if="!localIcon" />
          <icon-refresh v-else />
        </template>
        {{ localIcon ? 'AI 重新生成' : 'AI 生成图标' }}
      </a-button>
    </div>

    <!-- 提示文字 - 居中 -->
    <div class="text-center text-xs text-gray-500 leading-relaxed w-full">
      点击按钮上传自定义图标<br />或让 AI 根据名称智能生成
    </div>
  </a-space>
</template>

<style scoped>
/* 确保 Upload 组件完全居中 */
:deep(.centered-upload) {
  display: flex;
  justify-content: center;
  align-items: center;
}

:deep(.centered-upload .arco-upload) {
  display: flex;
  justify-content: center;
  align-items: center;
}

:deep(.centered-upload .arco-upload-list) {
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 0;
}

/* 上传按钮样式 */
:deep(.arco-upload-picture-card) {
  width: 140px;
  height: 140px;
  margin: 0;
  @apply rounded-2xl border-2 border-dashed border-gray-300 bg-white transition-all duration-300;
}

:deep(.arco-upload-picture-card:hover) {
  @apply border-blue-500 bg-gradient-to-br from-blue-50 to-blue-100 shadow-xl;
  transform: translateY(-4px);
}

/* 已上传图片样式 */
:deep(.arco-upload-list-picture-card) {
  width: 140px;
  height: 140px;
  margin: 0;
}

:deep(.arco-upload-list-item-picture) {
  width: 140px;
  height: 140px;
  @apply rounded-2xl border-2 border-gray-200 overflow-hidden transition-all duration-300;
}

:deep(.arco-upload-list-item-picture:hover) {
  @apply border-blue-500 shadow-xl;
  transform: translateY(-4px);
}

/* 确保图片和上传按钮在同一位置 */
:deep(.arco-upload-list-picture-card .arco-upload-list-item) {
  margin: 0;
}
</style>
