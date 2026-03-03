<script setup lang="ts">
import { ref, watch, computed, nextTick, defineAsyncComponent } from 'vue'
import AICodeAssistant from '@/components/AICodeAssistant.vue'

const PythonCodeEditor = defineAsyncComponent(
  () => import('@/components/PythonCodeEditor.vue'),
)

type EditorValidationIssue = {
  severity: number
}

type EditorValidation = {
  isValid: boolean
  errors: EditorValidationIssue[]
}

// 定义组件属性
const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  modelValue: {
    type: String,
    default: '',
  },
  title: {
    type: String,
    default: 'Python 代码编辑器',
  },
})

const emits = defineEmits(['update:visible', 'update:modelValue'])

// 本地状态（不能直接修改 props）
const localVisible = ref(props.visible)
const localCode = ref(props.modelValue)
const codeEditorRef = ref<unknown>(null)
const codeValidation = ref<EditorValidation>({ isValid: true, errors: [] })
const aiAssistantVisible = ref(false)

// 计算错误数量
const errorCount = computed(() => {
  return codeValidation.value.errors.filter((e) => e.severity === 8).length
})

const warningCount = computed(() => {
  return codeValidation.value.errors.filter((e) => e.severity === 4).length
})

// 处理代码验证
const handleCodeValidate = (validation: EditorValidation) => {
  codeValidation.value = validation
}

// 监听外部 visible 变化
watch(
  () => props.visible,
  (newValue) => {
    localVisible.value = newValue
  },
)

// 监听外部 modelValue 变化
watch(
  () => props.modelValue,
  (newValue) => {
    localCode.value = newValue
  },
)

// 监听本地 visible 变化，同步到外部
watch(localVisible, (newValue) => {
  emits('update:visible', newValue)
  if (!newValue) {
    aiAssistantVisible.value = false
  }
})

// 监听本地代码变化，同步到外部
watch(localCode, (newValue) => {
  emits('update:modelValue', newValue)
})

// 关闭模态框
const handleClose = () => {
  localVisible.value = false
}

// 打开 AI 助手
const openAIAssistant = () => {
  if (aiAssistantVisible.value) {
    aiAssistantVisible.value = false
    nextTick(() => {
      aiAssistantVisible.value = true
    })
    return
  }

  aiAssistantVisible.value = true
}

// 插入 AI 生成的代码
const handleInsertCode = (code: string) => {
  localCode.value = code
}
</script>

<template>
  <a-modal
    v-model:visible="localVisible"
    :width="'min(960px, 92vw)'"
    :footer="false"
    :mask-closable="true"
    unmount-on-close
    @cancel="handleClose"
  >
    <template #title>
      <div class="flex items-center justify-between w-full pr-10">
        <div class="flex items-center gap-3">
          <icon-code :size="24" class="text-cyan-500" />
          <span class="text-lg font-semibold">{{ title }}</span>
        </div>
        <div class="flex items-center gap-3">
          <!-- AI 助手按钮 -->
          <a-button type="primary" size="small" @click="openAIAssistant">
            <template #icon>
              <icon-robot />
            </template>
            Python代码生成AI助手
          </a-button>
          <!-- 状态标签 -->
          <a-tag v-if="errorCount > 0" size="medium" color="red">
            <template #icon>
              <icon-exclamation-circle />
            </template>
            {{ errorCount }} 个错误
          </a-tag>
          <a-tag v-else-if="warningCount > 0" size="medium" color="orange">
            <template #icon>
              <icon-info-circle />
            </template>
            {{ warningCount }} 个警告
          </a-tag>
          <a-tag v-else size="medium" color="green">
            <template #icon>
              <icon-check-circle />
            </template>
            代码正常
          </a-tag>
        </div>
      </div>
    </template>

    <div class="p-4">
      <!-- 代码编辑器提示 -->
      <a-alert type="info" class="mb-4">
        <template #icon>
          <icon-info-circle />
        </template>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4 text-sm">
            <span>• 函数名必须为 <code class="bg-blue-100 px-1 rounded">main(params)</code></span>
            <span>• 使用 <code class="bg-blue-100 px-1 rounded">params.get('key', default)</code> 获取参数</span>
            <span>• 返回字典对象，参数名需与输出参数一致</span>
          </div>
          <div class="flex items-center gap-2 text-xs text-gray-500">
            <span>Ctrl+S 保存</span>
            <span>|</span>
            <span>Ctrl+/ 注释</span>
            <span>|</span>
            <span>Esc 关闭</span>
          </div>
        </div>
      </a-alert>

      <!-- Python 代码编辑器 -->
      <python-code-editor
        ref="codeEditorRef"
        v-model="localCode"
        height="calc(68vh - 160px)"
        placeholder="# 在此编写 Python 代码
# 示例：
def main(params):
    # 从输入参数中获取变量
    x = int(params.get('x', 0))
    y = int(params.get('y', 0))

    # 执行业务逻辑
    result = x + y

    # 返回结果（参数名需与输出参数一致）
    return {
        'output': result
    }"
        @validate="handleCodeValidate"
      />
    </div>

    <!-- AI 代码助手 -->
    <AICodeAssistant
      v-model:visible="aiAssistantVisible"
      :current-code="localCode"
      @insert-code="handleInsertCode"
    />
  </a-modal>
</template>

<style scoped>
:deep(.arco-modal) {
  @apply top-5;
}

:deep(.arco-modal-header) {
  @apply border-b;
}

:deep(.arco-modal-body) {
  @apply p-0;
}
</style>
