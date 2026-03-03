<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, shallowRef } from 'vue'
import type * as Monaco from 'monaco-editor'
import { Message } from '@arco-design/web-vue'
import {
  validatePythonSyntax,
  checkCodeQuality,
  type ValidationError,
} from '@/utils/python-validator'

// 定义组件属性
const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  placeholder: {
    type: String,
    default: '# 在此编写 Python 代码...',
  },
  height: {
    type: String,
    default: '500px',
  },
  readonly: {
    type: Boolean,
    default: false,
  },
})

const emits = defineEmits(['update:modelValue', 'validate'])

// 编辑器实例和容器引用
const editorContainer = ref<HTMLElement | null>(null)
const monacoModule = shallowRef<typeof import('monaco-editor') | null>(null)
const editor = shallowRef<Monaco.editor.IStandaloneCodeEditor | null>(null)
const errors = ref<ValidationError[]>([])
const isValidating = ref(false)

// Python 语法验证函数（使用新的验证工具）
const validatePythonCode = (code: string): ValidationError[] => {
  if (!code || code.trim() === '') {
    return []
  }

  // 使用语法验证工具
  const syntaxResult = validatePythonSyntax(code)
  const qualitySuggestions = checkCodeQuality(code)

  // 合并所有验证结果
  return [...syntaxResult.errors, ...qualitySuggestions]
}

// 更新编辑器标记
const updateMarkers = (validationErrors: ValidationError[]) => {
  const monaco = monacoModule.value
  if (!editor.value || !monaco) return
  const model = editor.value.getModel()
  if (!model) return

  monaco.editor.setModelMarkers(model, 'python', validationErrors as Monaco.editor.IMarkerData[])
  errors.value = validationErrors
  emits('validate', {
    isValid: validationErrors.filter((error) => error.severity === 8).length === 0,
    errors: validationErrors,
  })
}

// 初始化编辑器
onMounted(async () => {
  if (!editorContainer.value) return
  const container = editorContainer.value
  const monaco = await import('monaco-editor')
  monacoModule.value = monaco

  // 配置 Monaco Editor
  editor.value = monaco.editor.create(container, {
    value: props.modelValue || props.placeholder,
    language: 'python',
    theme: 'vs-dark',
    automaticLayout: true,
    fontSize: 14,
    lineNumbers: 'on',
    roundedSelection: true,
    scrollBeyondLastLine: false,
    readOnly: props.readonly,
    minimap: {
      enabled: true,
    },
    scrollbar: {
      vertical: 'visible',
      horizontal: 'visible',
      useShadows: false,
      verticalScrollbarSize: 10,
      horizontalScrollbarSize: 10,
    },
    suggestOnTriggerCharacters: true,
    quickSuggestions: {
      other: true,
      comments: false,
      strings: false,
    },
    parameterHints: {
      enabled: true,
    },
    formatOnPaste: true,
    formatOnType: true,
    tabSize: 4,
    insertSpaces: true,
  })

  // 监听内容变化
  editor.value.onDidChangeModelContent(() => {
    if (editor.value) {
      const value = editor.value.getValue()
      emits('update:modelValue', value)

      // 实时验证
      isValidating.value = true
      const validationErrors = validatePythonCode(value)
      updateMarkers(validationErrors)
      isValidating.value = false
    }
  })

  // 初始验证
  if (props.modelValue) {
    const validationErrors = validatePythonCode(props.modelValue)
    updateMarkers(validationErrors)
  }

  // 添加自定义命令
  editor.value.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
    Message.success('代码已自动保存')
  })
})

// 监听外部值变化
watch(
  () => props.modelValue,
  (newValue) => {
    if (editor.value && newValue !== editor.value.getValue()) {
      editor.value.setValue(newValue || props.placeholder)
      const validationErrors = validatePythonCode(newValue)
      updateMarkers(validationErrors)
    }
  },
)

// 清理
onBeforeUnmount(() => {
  if (editor.value) {
    editor.value.dispose()
  }
})

// 暴露方法
defineExpose({
  getEditor: () => editor.value,
  validate: () => {
    if (editor.value) {
      const value = editor.value.getValue()
      const validationErrors = validatePythonCode(value)
      updateMarkers(validationErrors)
      return {
        isValid: validationErrors.filter((error) => error.severity === 8).length === 0,
        errors: validationErrors,
      }
    }
    return { isValid: true, errors: [] }
  },
})
</script>

<template>
  <div class="overflow-hidden rounded-lg border border-gray-300">
    <!-- 编辑器工具栏 -->
    <div class="border-b border-gray-700">
      <div class="flex items-center justify-between px-3 py-2 bg-gray-800 text-white text-xs">
        <div class="flex items-center gap-2">
          <icon-code :size="16" />
          <span>Python 代码编辑器</span>
          <a-tag v-if="isValidating" size="small" color="blue">验证中...</a-tag>
          <a-tag v-else-if="errors.length === 0" size="small" color="green">
            <template #icon>
              <icon-check-circle />
            </template>
            无错误
          </a-tag>
          <a-tag v-else size="small" color="red">
            <template #icon>
              <icon-close-circle />
            </template>
            {{ errors.filter(e => e.severity === 8).length }} 个错误
          </a-tag>
        </div>
        <div class="flex items-center gap-2 text-gray-400">
          <span>Ctrl+S 保存</span>
          <span>|</span>
          <span>Ctrl+/ 注释</span>
        </div>
      </div>
    </div>

    <!-- Monaco 编辑器容器 -->
    <div
      ref="editorContainer"
      class="w-full"
      :style="{ height: height }"
    ></div>

    <!-- 错误提示面板 -->
    <div v-if="errors.length > 0" class="error-panel max-h-32 overflow-y-auto">
      <div class="px-3 py-2 bg-red-50 border-t border-red-200">
        <div class="text-xs font-semibold text-red-700 mb-2">代码问题：</div>
        <div class="space-y-1">
          <div
            v-for="(error, index) in errors.slice(0, 5)"
            :key="index"
            class="text-xs flex items-start gap-2"
          >
            <icon-exclamation-circle-fill
              v-if="error.severity === 8"
              class="text-red-500 flex-shrink-0 mt-0.5"
              :size="14"
            />
            <icon-info-circle-fill
              v-else
              class="text-orange-500 flex-shrink-0 mt-0.5"
              :size="14"
            />
            <span class="text-gray-700">
              <span class="font-mono text-red-600">行 {{ error.startLineNumber }}:</span>
              {{ error.message }}
            </span>
          </div>
          <div v-if="errors.length > 5" class="text-xs text-gray-500 pl-5">
            还有 {{ errors.length - 5 }} 个问题...
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.error-panel {
  scrollbar-width: thin;
  scrollbar-color: rgba(156, 163, 175, 0.5) transparent;
}

.error-panel::-webkit-scrollbar {
  width: 6px;
}

.error-panel::-webkit-scrollbar-track {
  background: transparent;
}

.error-panel::-webkit-scrollbar-thumb {
  background-color: rgba(156, 163, 175, 0.5);
  border-radius: 3px;
}

.error-panel::-webkit-scrollbar-thumb:hover {
  background-color: rgba(156, 163, 175, 0.8);
}
</style>
