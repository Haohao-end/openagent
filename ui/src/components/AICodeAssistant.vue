<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { codeAssistantChat } from '@/services/ai'
import { useMarkdownRenderer } from '@/hooks/use-markdown-renderer'
import { getErrorMessage } from '@/utils/error'
import 'github-markdown-css'
import 'highlight.js/styles/github.css'

const { renderMarkdown, handleMarkdownCopyClick } = useMarkdownRenderer()

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  currentCode: {
    type: String,
    default: '',
  },
})

const emits = defineEmits(['update:visible', 'insert-code'])

const localVisible = computed({
  get: () => props.visible,
  set: (value: boolean) => emits('update:visible', value),
})

const userQuestion = ref('')
const aiResponse = ref('')
const isLoading = ref(false)

watch(
  () => props.visible,
  (newVisible) => {
    if (newVisible) {
      userQuestion.value = ''
      aiResponse.value = ''
    }
  },
)

const extractPythonCode = (content: string): string => {
  const pythonFence = content.match(/```python\s*([\s\S]*?)```/i)
  if (pythonFence?.[1]) {
    return pythonFence[1].trim()
  }

  const genericFence = content.match(/```[\w-]*\s*([\s\S]*?)```/)
  if (genericFence?.[1]) {
    return genericFence[1].trim()
  }

  return ''
}

const generatedCode = computed(() => extractPythonCode(aiResponse.value))
const canUseCode = computed(() => generatedCode.value.trim() !== '')

const handleClose = () => {
  localVisible.value = false
}

const handleSubmit = async () => {
  const question = userQuestion.value.trim()
  if (!question) {
    Message.warning('请输入需求描述')
    return
  }

  isLoading.value = true
  aiResponse.value = ''

  try {
    const response = await codeAssistantChat(question, (eventResponse) => {
      const content = String(eventResponse?.data?.content ?? '')
      if (!content) return
      aiResponse.value += content
    })

    if (response && typeof response === 'object' && 'code' in response) {
      throw new Error(String((response as { message?: string }).message || 'AI 请求失败'))
    }

    if (!aiResponse.value.trim()) {
      Message.warning('AI 未返回内容，请重试')
    }
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, 'AI 请求失败，请稍后重试'))
  } finally {
    isLoading.value = false
  }
}

const handleInsertCode = () => {
  if (!canUseCode.value) {
    Message.warning('未检测到可插入的代码块')
    return
  }

  emits('insert-code', generatedCode.value)
  Message.success('代码已插入')
  handleClose()
}

const handleMarkdownClick = async (event: MouseEvent) => {
  await handleMarkdownCopyClick(event)
}
</script>

<template>
  <teleport to="body">
    <div
      v-if="localVisible"
      class="fixed inset-0 z-[1200] flex items-center justify-center bg-black/40 p-4"
      @click.self="handleClose"
    >
      <div class="w-full max-w-[760px] rounded-xl border border-gray-200 bg-white shadow-2xl" @click.stop>
        <div class="flex h-12 items-center justify-between border-b border-gray-200 px-4">
          <div class="flex items-center gap-2">
            <icon-robot class="text-blue-600" :size="18" />
            <span class="text-sm font-semibold text-gray-800">Python代码生成AI助手</span>
          </div>
          <a-button type="text" size="mini" class="!text-gray-500" @click="handleClose">
            <template #icon>
              <icon-close />
            </template>
          </a-button>
        </div>

        <div class="flex flex-col gap-3 p-4">
          <div v-if="aiResponse || isLoading" class="max-h-[360px] overflow-y-auto rounded-lg border border-gray-200 bg-gray-50 p-3">
            <div v-if="isLoading" class="mb-2 flex items-center gap-2 text-xs text-gray-500">
              <a-spin size="14" />
              <span>AI 正在生成代码...</span>
            </div>

            <div
              v-if="aiResponse"
              class="assistant-markdown markdown-body"
              v-html="renderMarkdown(aiResponse)"
              @click="handleMarkdownClick"
            ></div>

            <div class="mt-3 flex items-center gap-2">
              <a-button type="primary" size="small" :disabled="!canUseCode" @click="handleInsertCode">
                <template #icon>
                  <icon-plus />
                </template>
                插入编辑器
              </a-button>
            </div>
          </div>

          <div class="flex h-[50px] items-center gap-2 rounded-full border border-gray-200 px-4">
            <input
              v-model="userQuestion"
              type="text"
              class="flex-1 bg-transparent text-sm outline-0"
              :disabled="isLoading"
              placeholder="描述你想要的 Python 代码，例如：解析参数并返回统计结果"
              @keydown.enter.prevent="handleSubmit"
            />
            <a-button
              type="text"
              shape="circle"
              :loading="isLoading"
              :disabled="isLoading"
              @click="handleSubmit"
            >
              <template #icon>
                <icon-send :size="16" class="!text-blue-700" />
              </template>
            </a-button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
:deep(.assistant-markdown) {
  @apply text-sm leading-relaxed;
}

:deep(.assistant-markdown pre) {
  @apply bg-gray-900 text-gray-100 p-3 rounded-lg overflow-x-auto my-2;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
  line-height: 1.6;
}

:deep(.assistant-markdown pre code) {
  @apply bg-transparent text-gray-100 p-0;
}

:deep(.assistant-markdown code) {
  @apply bg-blue-100 text-blue-800 px-1 py-0.5 rounded text-xs;
}

:deep(.assistant-markdown .md-code-block) {
  @apply my-2 border border-gray-200 rounded-lg overflow-hidden;
}

:deep(.assistant-markdown .md-code-header) {
  @apply h-8 px-3 flex items-center justify-between bg-white border-b border-gray-200;
}

:deep(.assistant-markdown .md-code-lang) {
  @apply text-xs text-gray-500;
}

:deep(.assistant-markdown .md-code-copy-btn) {
  @apply text-xs text-gray-700 bg-transparent border-0 cursor-pointer;
}

:deep(.assistant-markdown .md-code-copy-btn:hover) {
  @apply text-gray-900;
}

:deep(.assistant-markdown .md-code-copy-btn:disabled) {
  @apply text-gray-400 cursor-default;
}
</style>
