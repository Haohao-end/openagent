<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import hljs from 'highlight.js/lib/common'
import 'highlight.js/styles/github.css'

// 1.定义自定义组件所需数据
const props = defineProps({
  language: { type: String, default: '', required: true },
  copyable: { type: Boolean, default: true },
})
const codeElement = ref<HTMLElement | null>(null)

// 2.组件在挂载成功后高亮代码
onMounted(() => {
  if (codeElement.value) hljs.highlightElement(codeElement.value)
})

// 3.复制代码功能
const copyCode = () => {
  const code = codeElement.value?.textContent || ''
  navigator.clipboard.writeText(code).then(() => {
    Message.success('已复制到剪贴板')
  }).catch(() => {
    Message.error('复制失败')
  })
}
</script>

<template>
  <div class="relative group mb-4">
    <pre
      class="!mb-0"
    ><code ref="codeElement" :class="`language-${props.language} whitespace-pre`"><slot></slot></code></pre>
    <button
      v-if="copyable"
      @click="copyCode"
      class="absolute top-2 right-2 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
      </svg>
      复制
    </button>
  </div>
</template>

<style scoped></style>
