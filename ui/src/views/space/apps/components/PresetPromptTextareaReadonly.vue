<script setup lang="ts">
import { ref, computed } from 'vue'
import { useMarkdownRenderer } from '@/hooks/use-markdown-renderer'
import 'github-markdown-css'
import 'highlight.js/styles/github.css'

// 只读版本的人设与回复逻辑组件，支持编辑、对比、预览三种模式

const props = defineProps({
  preset_prompt: { type: String, default: '', required: true },
})

// 显示模式: edit(编辑), preview(预览), split(对比)
const mode = ref<'edit' | 'preview' | 'split'>('edit')

// 同步滚动相关
const editorPaneRef = ref<HTMLDivElement>()
const previewPaneRef = ref<HTMLDivElement>()

let editorScrollTimer: number | null = null
let previewScrollTimer: number | null = null
let isEditorScrolling = false
let isPreviewScrolling = false

const { renderMarkdownWithPlaceholder, handleMarkdownCopyClick } = useMarkdownRenderer({
  typographer: true,
})

// 同步滚动：从编辑区到预览区
const syncScrollFromEditor = () => {
  if (!editorPaneRef.value || !previewPaneRef.value) return
  if (mode.value !== 'split') return

  // 如果是预览区正在滚动（被动同步），不要触发反向同步
  if (isPreviewScrolling) return

  // 标记编辑区正在滚动
  isEditorScrolling = true

  // 清除之前的定时器
  if (editorScrollTimer) {
    clearTimeout(editorScrollTimer)
  }

  const editor = editorPaneRef.value
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

// 同步滚动：从预览区到编辑区
const syncScrollFromPreview = () => {
  if (!editorPaneRef.value || !previewPaneRef.value) return
  if (mode.value !== 'split') return

  // 如果是编辑区正在滚动（被动同步），不要触发反向同步
  if (isEditorScrolling) return

  // 标记预览区正在滚动
  isPreviewScrolling = true

  // 清除之前的定时器
  if (previewScrollTimer) {
    clearTimeout(previewScrollTimer)
  }

  const editor = editorPaneRef.value
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

// 渲染 Markdown
const compiledMarkdown = computed(() => {
  return renderMarkdownWithPlaceholder(props.preset_prompt, '暂无人设与回复逻辑')
})

// 处理代码块复制
const handleMarkdownClick = async (event: MouseEvent) => {
  await handleMarkdownCopyClick(event, { successMessage: '代码已复制' })
}
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-173px)]">
    <!-- 提示标题 -->
    <div class="flex items-center justify-between px-4 mb-4">
      <div class="text-gray-700 font-bold">人设与回复逻辑</div>
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
          预览
        </a-button>
      </a-space>
    </div>

    <!-- 内容区域 -->
    <div class="flex-1 min-h-0 px-4">
      <div class="readonly-editor-container" :class="{ 'split-mode': mode === 'split' }">
        <!-- 编辑模式（只读文本） -->
        <div
          v-show="mode === 'edit' || mode === 'split'"
          ref="editorPaneRef"
          class="editor-pane"
          @scroll="syncScrollFromEditor"
        >
          <div class="readonly-textarea">
            {{ props.preset_prompt || '暂无人设与回复逻辑' }}
          </div>
        </div>

        <!-- 预览模式（Markdown 渲染） -->
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
  </div>
</template>

<style scoped>
.toolbar-btn {
  border-radius: 6px;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  background: #e5e7eb;
}

.readonly-editor-container {
  display: flex;
  height: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.readonly-editor-container.split-mode {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.editor-pane {
  flex: 1;
  overflow-y: auto;
  background: #f9fafb;
  min-height: 0;
  scroll-behavior: auto; /* 禁用平滑滚动，避免抖动 */
  will-change: scroll-position; /* 提示浏览器优化滚动性能 */
  transform: translateZ(0); /* 启用硬件加速 */
}

.split-mode .editor-pane {
  border-right: 1px solid #e5e7eb;
}

.readonly-textarea {
  padding: 16px;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono',
    monospace;
  font-size: 14px;
  line-height: 1.6;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-word;
}

.preview-pane {
  flex: 1;
  overflow-y: auto;
  background: #fff;
  min-height: 0;
  scroll-behavior: auto; /* 禁用平滑滚动，避免抖动 */
  will-change: scroll-position; /* 提示浏览器优化滚动性能 */
  transform: translateZ(0); /* 启用硬件加速 */
}

.preview-content {
  padding: 16px;
}

/* 隐藏滚动条但保持滚动功能 */
.editor-pane,
.preview-pane {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.editor-pane::-webkit-scrollbar,
.preview-pane::-webkit-scrollbar {
  display: none;
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
</style>
