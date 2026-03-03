<script setup lang="ts">
import { ref, computed } from 'vue'
import { useMarkdownRenderer } from '@/hooks/use-markdown-renderer'
import 'github-markdown-css'
import 'highlight.js/styles/github.css'

const props = defineProps({
  modelValue: { type: String, default: '', required: true },
  placeholder: { type: String, default: '请输入内容，支持 Markdown 格式' },
  maxLength: { type: Number, default: 5000 },
  minHeight: { type: String, default: '200px' },
  showToolbar: { type: Boolean, default: true },
  defaultMode: { type: String as () => 'edit' | 'preview' | 'split', default: 'edit' },
})

const emits = defineEmits(['update:modelValue', 'blur'])

// 编辑模式: edit(编辑), preview(预览), split(分屏)
const mode = ref<'edit' | 'preview' | 'split'>(props.defaultMode)
const textareaRef = ref<HTMLTextAreaElement>()
const previewPaneRef = ref<HTMLDivElement>()

// 同步滚动相关 - 重新设计
let editorScrollTimer: number | null = null
let previewScrollTimer: number | null = null
let isEditorScrolling = false
let isPreviewScrolling = false

// 同步滚动：从编辑区到预览区（终极优化版）
const syncScrollFromEditor = () => {
  if (!textareaRef.value || !previewPaneRef.value) return
  if (mode.value !== 'split') return

  // 如果是预览区正在滚动（被动同步），不要触发反向同步
  if (isPreviewScrolling) return

  // 标记编辑区正在滚动
  isEditorScrolling = true

  // 清除之前的定时器
  if (editorScrollTimer) {
    clearTimeout(editorScrollTimer)
  }

  const editor = textareaRef.value
  const preview = previewPaneRef.value

  // 立即同步滚动位置
  const editorScrollHeight = editor.scrollHeight - editor.clientHeight
  if (editorScrollHeight <= 0) return

  const scrollPercentage = editor.scrollTop / editorScrollHeight
  const previewScrollHeight = preview.scrollHeight - preview.clientHeight

  preview.scrollTop = scrollPercentage * previewScrollHeight

  // 100ms 后重置标志位（滚动结束）
  editorScrollTimer = window.setTimeout(() => {
    isEditorScrolling = false
  }, 100)
}

// 同步滚动：从预览区到编辑区（终极优化版）
const syncScrollFromPreview = () => {
  if (!textareaRef.value || !previewPaneRef.value) return
  if (mode.value !== 'split') return

  // 如果是编辑区正在滚动（被动同步），不要触发反向同步
  if (isEditorScrolling) return

  // 标记预览区正在滚动
  isPreviewScrolling = true

  // 清除之前的定时器
  if (previewScrollTimer) {
    clearTimeout(previewScrollTimer)
  }

  const editor = textareaRef.value
  const preview = previewPaneRef.value

  // 立即同步滚动位置
  const previewScrollHeight = preview.scrollHeight - preview.clientHeight
  if (previewScrollHeight <= 0) return

  const scrollPercentage = preview.scrollTop / previewScrollHeight
  const editorScrollHeight = editor.scrollHeight - editor.clientHeight

  editor.scrollTop = scrollPercentage * editorScrollHeight

  // 100ms 后重置标志位（滚动结束）
  previewScrollTimer = window.setTimeout(() => {
    isPreviewScrolling = false
  }, 100)
}

const { renderMarkdownWithPlaceholder, handleMarkdownCopyClick } = useMarkdownRenderer({
  typographer: true,
})

// 渲染 Markdown
const compiledMarkdown = computed(() => {
  return renderMarkdownWithPlaceholder(props.modelValue, '暂无内容')
})

// 字数统计
const wordCount = computed(() => props.modelValue.length)

// 处理输入
const handleInput = (event: Event) => {
  const target = event.target as HTMLTextAreaElement
  emits('update:modelValue', target.value)
}

// 处理失焦
const handleBlur = () => {
  emits('blur')
}

// 插入 Markdown 语法
const insertMarkdown = (syntax: string, placeholder = '') => {
  if (!textareaRef.value) return

  const textarea = textareaRef.value
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const selectedText = props.modelValue.substring(start, end)
  const textToInsert = selectedText || placeholder

  let newText = ''
  let cursorOffset = 0

  switch (syntax) {
    case 'bold':
      newText = `**${textToInsert}**`
      cursorOffset = textToInsert ? newText.length : 2
      break
    case 'italic':
      newText = `*${textToInsert}*`
      cursorOffset = textToInsert ? newText.length : 1
      break
    case 'code':
      newText = `\`${textToInsert}\``
      cursorOffset = textToInsert ? newText.length : 1
      break
    case 'codeblock':
      newText = `\n\`\`\`\n${textToInsert}\n\`\`\`\n`
      cursorOffset = textToInsert ? newText.length : 5
      break
    case 'link':
      newText = `[${textToInsert || '链接文本'}](url)`
      cursorOffset = textToInsert ? newText.length - 4 : 1
      break
    case 'ul':
      newText = `\n- ${textToInsert || '列表项'}\n`
      cursorOffset = textToInsert ? newText.length : 3
      break
    case 'ol':
      newText = `\n1. ${textToInsert || '列表项'}\n`
      cursorOffset = textToInsert ? newText.length : 4
      break
    case 'quote':
      newText = `\n> ${textToInsert || '引用内容'}\n`
      cursorOffset = textToInsert ? newText.length : 3
      break
    case 'h1':
      newText = `\n# ${textToInsert || '一级标题'}\n`
      cursorOffset = textToInsert ? newText.length : 3
      break
    case 'h2':
      newText = `\n## ${textToInsert || '二级标题'}\n`
      cursorOffset = textToInsert ? newText.length : 4
      break
    case 'h3':
      newText = `\n### ${textToInsert || '三级标题'}\n`
      cursorOffset = textToInsert ? newText.length : 5
      break
    default:
      return
  }

  const before = props.modelValue.substring(0, start)
  const after = props.modelValue.substring(end)
  const updatedValue = before + newText + after

  emits('update:modelValue', updatedValue)

  // 恢复焦点和光标位置
  setTimeout(() => {
    textarea.focus()
    const newCursorPos = start + cursorOffset
    textarea.setSelectionRange(newCursorPos, newCursorPos)
  }, 0)
}

// 处理代码块复制
const handleMarkdownClick = async (event: MouseEvent) => {
  await handleMarkdownCopyClick(event, { successMessage: '代码已复制' })
}
</script>

<template>
  <div class="markdown-editor">
    <!-- 工具栏 -->
    <div v-if="props.showToolbar" class="editor-toolbar">
      <a-space :size="4">
        <!-- 标题 -->
        <a-dropdown trigger="hover" position="bottom">
          <a-button size="mini" class="toolbar-btn">
            <template #icon>
              <icon-font-colors />
            </template>
          </a-button>
          <template #content>
            <a-doption @click="insertMarkdown('h1')">
              <span class="text-2xl font-bold">H1</span>
            </a-doption>
            <a-doption @click="insertMarkdown('h2')">
              <span class="text-xl font-bold">H2</span>
            </a-doption>
            <a-doption @click="insertMarkdown('h3')">
              <span class="text-lg font-bold">H3</span>
            </a-doption>
          </template>
        </a-dropdown>

        <a-divider direction="vertical" class="!my-0" />

        <!-- 文本样式 -->
        <a-button size="mini" class="toolbar-btn" @click="insertMarkdown('bold')">
          <template #icon>
            <icon-bold />
          </template>
        </a-button>
        <a-button size="mini" class="toolbar-btn" @click="insertMarkdown('italic')">
          <template #icon>
            <icon-italic />
          </template>
        </a-button>

        <a-divider direction="vertical" class="!my-0" />

        <!-- 列表 -->
        <a-button size="mini" class="toolbar-btn" @click="insertMarkdown('ul')">
          <template #icon>
            <icon-unordered-list />
          </template>
        </a-button>
        <a-button size="mini" class="toolbar-btn" @click="insertMarkdown('ol')">
          <template #icon>
            <icon-ordered-list />
          </template>
        </a-button>

        <a-divider direction="vertical" class="!my-0" />

        <!-- 其他 -->
        <a-button size="mini" class="toolbar-btn" @click="insertMarkdown('quote')">
          <template #icon>
            <icon-quote />
          </template>
        </a-button>
        <a-button size="mini" class="toolbar-btn" @click="insertMarkdown('code')">
          <template #icon>
            <icon-code />
          </template>
        </a-button>
        <a-button size="mini" class="toolbar-btn" @click="insertMarkdown('codeblock')">
          <template #icon>
            <icon-code-block />
          </template>
        </a-button>
        <a-button size="mini" class="toolbar-btn" @click="insertMarkdown('link')">
          <template #icon>
            <icon-link />
          </template>
        </a-button>
      </a-space>

      <!-- 右侧操作 -->
      <a-space :size="4">
        <a-button
          size="mini"
          :type="mode === 'edit' ? 'primary' : 'text'"
          class="toolbar-btn"
          @click="mode = 'edit'"
        >
          <template #icon>
            <icon-edit />
          </template>
          编辑
        </a-button>
        <a-button
          size="mini"
          :type="mode === 'split' ? 'primary' : 'text'"
          class="toolbar-btn"
          @click="mode = 'split'"
        >
          <template #icon>
            <icon-apps />
          </template>
          对比
        </a-button>
        <a-button
          size="mini"
          :type="mode === 'preview' ? 'primary' : 'text'"
          class="toolbar-btn"
          @click="mode = 'preview'"
        >
          <template #icon>
            <icon-eye />
          </template>
          浏览
        </a-button>
      </a-space>
    </div>

    <!-- 编辑器主体 -->
    <div class="editor-body" :class="{ 'split-mode': mode === 'split' }">
      <!-- 编辑区 -->
      <div v-show="mode === 'edit' || mode === 'split'" class="editor-pane">
        <textarea
          ref="textareaRef"
          :value="props.modelValue"
          :placeholder="props.placeholder"
          :maxlength="props.maxLength"
          class="editor-textarea"
          @input="handleInput"
          @blur="handleBlur"
          @scroll="syncScrollFromEditor"
        />
        <div class="editor-footer">
          <span class="text-xs text-gray-400">
            {{ wordCount }} / {{ props.maxLength }}
          </span>
        </div>
      </div>

      <!-- 预览区 -->
      <div
        v-show="mode === 'preview' || mode === 'split'"
        ref="previewPaneRef"
        class="preview-pane"
        @scroll="syncScrollFromPreview"
      >
        <div
          class="markdown-body preview-content"
          v-html="compiledMarkdown"
          @click="handleMarkdownClick"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.markdown-editor {
  display: flex;
  flex-direction: column;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  height: 100%; /* 关键：占满父容器高度 */
}

.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}

.toolbar-btn {
  border-radius: 6px;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  background: #e5e7eb;
}

.editor-body {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0; /* 关键：允许 flex 子元素正确计算高度 */
}

.editor-body.split-mode {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 600px;
}

.editor-pane {
  display: flex;
  flex-direction: column;
  flex: 1;
  position: relative;
  overflow: hidden;
  min-height: 0; /* 关键：允许 flex 子元素正确计算高度 */
}

.split-mode .editor-pane {
  border-right: 1px solid #e5e7eb;
}

.editor-textarea {
  flex: 1;
  width: 100%;
  padding: 16px;
  border: none;
  outline: none;
  resize: none;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono',
    monospace;
  font-size: 14px;
  line-height: 1.6;
  color: #374151;
  background: transparent;
  overflow-y: auto;
  scroll-behavior: auto; /* 禁用平滑滚动，避免抖动 */
  will-change: scroll-position; /* 提示浏览器优化滚动性能 */
  transform: translateZ(0); /* 启用硬件加速 */
}

.editor-textarea::placeholder {
  color: #9ca3af;
}

/* 隐藏滚动条但保持滚动功能 */
.editor-textarea {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.editor-textarea::-webkit-scrollbar {
  display: none; /* Chrome, Safari, Opera */
}

.editor-footer {
  padding: 8px 16px;
  border-top: 1px solid #f3f4f6;
  background: #fafafa;
  display: flex;
  justify-content: flex-end;
}

.preview-pane {
  flex: 1;
  overflow-y: auto;
  background: #fff;
  min-height: 0; /* 关键：允许 flex 子元素正确计算高度 */
  scroll-behavior: auto; /* 禁用平滑滚动，避免抖动 */
  will-change: scroll-position; /* 提示浏览器优化滚动性能 */
  transform: translateZ(0); /* 启用硬件加速 */
}

.preview-content {
  padding: 16px;
  background: transparent;
}

/* 隐藏预览区滚动条但保持滚动功能 */
.preview-pane {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.preview-pane::-webkit-scrollbar {
  display: none; /* Chrome, Safari, Opera */
}

/* Markdown 样式增强 */
:deep(.markdown-body) {
  background: transparent;
  font-size: 14px;
}

:deep(.markdown-body h1) {
  font-size: 1.875rem;
  font-weight: 700;
  margin-top: 1.5rem;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #e5e7eb;
  color: #111827;
}

:deep(.markdown-body h2) {
  font-size: 1.5rem;
  font-weight: 600;
  margin-top: 1.25rem;
  margin-bottom: 0.75rem;
  padding-bottom: 0.375rem;
  border-bottom: 1px solid #e5e7eb;
  color: #1f2937;
}

:deep(.markdown-body h3) {
  font-size: 1.25rem;
  font-weight: 600;
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  color: #374151;
}

:deep(.markdown-body h4) {
  font-size: 1.125rem;
  font-weight: 600;
  margin-top: 0.875rem;
  margin-bottom: 0.5rem;
  color: #4b5563;
}

:deep(.markdown-body h5),
:deep(.markdown-body h6) {
  font-size: 1rem;
  font-weight: 600;
  margin-top: 0.75rem;
  margin-bottom: 0.5rem;
  color: #6b7280;
}

:deep(.markdown-body p) {
  margin-bottom: 1rem;
  line-height: 1.75;
  color: #374151;
}

:deep(.markdown-body ul),
:deep(.markdown-body ol) {
  margin-bottom: 1rem;
  padding-left: 1.5rem;
}

:deep(.markdown-body li) {
  margin-bottom: 0.375rem;
  line-height: 1.75;
  color: #374151;
}

:deep(.markdown-body blockquote) {
  margin: 1rem 0;
  padding: 0.75rem 1rem;
  border-left: 4px solid #3b82f6;
  background: #eff6ff;
  color: #1e40af;
  border-radius: 0 6px 6px 0;
}

:deep(.markdown-body blockquote p) {
  margin: 0;
}

:deep(.markdown-body code) {
  padding: 0.125rem 0.375rem;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  font-size: 0.875em;
  color: #dc2626;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono',
    monospace;
}

:deep(.markdown-body .md-code-block) {
  margin: 1rem 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

:deep(.markdown-body .md-code-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}

:deep(.markdown-body .md-code-lang) {
  color: #6b7280;
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
}

:deep(.markdown-body .md-code-copy-btn) {
  border: none;
  background: transparent;
  color: #374151;
  font-size: 12px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.2s;
}

:deep(.markdown-body .md-code-copy-btn:hover) {
  background: #e5e7eb;
  color: #111827;
}

:deep(.markdown-body .md-code-copy-btn:disabled) {
  color: #9ca3af;
  cursor: default;
  background: transparent;
}

:deep(.markdown-body pre.hljs) {
  margin: 0;
  border: 0;
  border-radius: 0;
  padding: 16px;
  background: #ffffff;
}

:deep(.markdown-body a) {
  color: #3b82f6;
  text-decoration: none;
  transition: color 0.2s;
}

:deep(.markdown-body a:hover) {
  color: #2563eb;
  text-decoration: underline;
}

:deep(.markdown-body hr) {
  margin: 1.5rem 0;
  border: none;
  border-top: 2px solid #e5e7eb;
}

:deep(.markdown-body table) {
  width: 100%;
  margin: 1rem 0;
  border-collapse: collapse;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
}

:deep(.markdown-body th) {
  background: #f9fafb;
  padding: 0.75rem;
  text-align: left;
  font-weight: 600;
  color: #374151;
  border-bottom: 2px solid #e5e7eb;
}

:deep(.markdown-body td) {
  padding: 0.75rem;
  border-bottom: 1px solid #f3f4f6;
  color: #4b5563;
}

:deep(.markdown-body tr:last-child td) {
  border-bottom: none;
}
</style>
