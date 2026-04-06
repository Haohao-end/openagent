<script setup lang="ts">
import { computed } from 'vue'
import { apiPrefix } from '@/config'

// 只读版本的应用能力组件
const props = defineProps({
  draft_app_config: { type: Object, required: true },
})

const defaultActivateKeys = [
  'tools',
  'workflows',
  'datasets',
  'long_term_memory',
  'opening',
  'suggested_after_answer',
  'review_config',
  'speech_to_text',
  'text_to_speech',
]

// 计算各项能力的状态
const toolsCount = computed(() => props.draft_app_config?.tools?.length || 0)
const workflowsCount = computed(() => props.draft_app_config?.workflows?.length || 0)
const datasetsCount = computed(() => props.draft_app_config?.datasets?.length || 0)
const longTermMemoryEnabled = computed(() => props.draft_app_config?.long_term_memory?.enable || false)
const openingStatementEnabled = computed(() => !!props.draft_app_config?.opening_statement)
const openingQuestionsCount = computed(() => props.draft_app_config?.opening_questions?.length || 0)
const suggestedAfterAnswerEnabled = computed(() => props.draft_app_config?.suggested_after_answer?.enable || false)
const speechToTextEnabled = computed(() => props.draft_app_config?.speech_to_text?.enable || false)
const textToSpeechEnabled = computed(() => props.draft_app_config?.text_to_speech?.enable || false)
const reviewConfigEnabled = computed(() => props.draft_app_config?.review_config?.enable || false)

// 统一处理图标地址，兼容绝对地址、相对地址以及 /api 路径
const normalizeIconUrl = (icon: string = '') => {
  if (!icon) return ''
  if (icon.startsWith('data:') || /^https?:\/\//.test(icon)) return icon
  const fallbackOrigin = globalThis.location?.origin ?? 'http://localhost'
  const apiUrl = new URL(apiPrefix, fallbackOrigin)
  const basePath = apiUrl.pathname.replace(/\/+$/, '')
  let path = icon.startsWith('/') ? icon : `/${icon}`

  // 本地开发常见：后端实际无 /api 前缀，但返回了 /api/xxx
  if (path.startsWith('/api/') && !basePath.startsWith('/api')) {
    path = path.replace(/^\/api/, '')
  }

  if (basePath && basePath !== '/' && !path.startsWith(`${basePath}/`)) {
    if (path.startsWith('/api/')) {
      path = path.replace(/^\/api/, '')
    }
    return `${apiUrl.origin}${basePath}${path}`
  }

  return `${apiUrl.origin}${path}`
}
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-141px)]">
    <!-- 应用能力标题 -->
    <div class="p-4 flex items-center justify-between">
      <div class="text-gray-700 font-bold">应用能力</div>
      <a-tag color="orange" size="small">预览模式</a-tag>
    </div>
    <!-- 应用能力列表 -->
    <div class="flex-1 overflow-scroll scrollbar-w-none">
      <a-collapse :bordered="false" :default-active-key="defaultActivateKeys" class="app-ability-readonly">
        <template #expand-icon="{ active }">
          <icon-down v-if="active" />
          <icon-right v-else />
        </template>

        <!-- 扩展插件 -->
        <a-collapse-item key="tools" header="扩展插件" class="app-ability-item">
          <div v-if="toolsCount > 0" class="space-y-2">
            <div
              v-for="(tool, index) in props.draft_app_config.tools"
              :key="index"
              class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
            >
              <a-avatar :size="32" shape="square" class="rounded-lg flex-shrink-0">
                <img v-if="tool.provider?.icon" :src="normalizeIconUrl(tool.provider.icon)" />
                <icon-apps v-else />
              </a-avatar>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-gray-700 truncate">
                  {{ tool.tool?.label || tool.tool?.name || '未命名工具' }}
                </div>
                <div class="text-xs text-gray-500 truncate">
                  {{ tool.provider?.label || tool.provider?.name || '未知提供者' }}
                </div>
              </div>
            </div>
          </div>
          <div v-else class="text-gray-400 text-sm">未配置扩展插件</div>
        </a-collapse-item>

        <!-- 工作流 -->
        <a-collapse-item key="workflows" header="工作流" class="app-ability-item">
          <div v-if="workflowsCount > 0" class="space-y-2">
            <div
              v-for="(workflow, index) in props.draft_app_config.workflows"
              :key="index"
              class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
            >
              <a-avatar :size="32" shape="square" class="rounded-lg flex-shrink-0">
                <img v-if="workflow.icon" :src="workflow.icon" />
                <icon-apps v-else />
              </a-avatar>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-gray-700 truncate">
                  {{ workflow.name || '未命名工作流' }}
                </div>
              </div>
            </div>
          </div>
          <div v-else class="text-gray-400 text-sm">未配置工作流</div>
        </a-collapse-item>

        <!-- 知识库 -->
        <a-collapse-item key="datasets" header="知识库" class="app-ability-item">
          <div v-if="datasetsCount > 0" class="space-y-2">
            <div
              v-for="(dataset, index) in props.draft_app_config.datasets"
              :key="index"
              class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
            >
              <a-avatar :size="32" shape="square" class="rounded-lg flex-shrink-0">
                <icon-storage />
              </a-avatar>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-gray-700 truncate">
                  {{ dataset.name || '未命名知识库' }}
                </div>
              </div>
            </div>
          </div>
          <div v-else class="text-gray-400 text-sm">未配置知识库</div>
        </a-collapse-item>

        <!-- 长期记忆召回 -->
        <a-collapse-item key="long_term_memory" header="长期记忆召回" class="app-ability-item">
          <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-700">状态</span>
            <a-tag :color="longTermMemoryEnabled ? 'green' : 'gray'" size="small">
              {{ longTermMemoryEnabled ? '已启用' : '未启用' }}
            </a-tag>
          </div>
        </a-collapse-item>

        <!-- 对话开场白 -->
        <a-collapse-item key="opening" header="对话开场白" class="app-ability-item">
          <div class="space-y-3">
            <div v-if="openingStatementEnabled" class="p-3 bg-gray-50 rounded-lg">
              <div class="text-xs text-gray-500 mb-1">开场白</div>
              <div class="text-sm text-gray-700 whitespace-pre-wrap">
                {{ props.draft_app_config.opening_statement }}
              </div>
            </div>
            <div v-if="openingQuestionsCount > 0" class="space-y-2">
              <div class="text-xs text-gray-500">开场问题 ({{ openingQuestionsCount }})</div>
              <div
                v-for="(question, index) in props.draft_app_config.opening_questions"
                :key="index"
                class="p-2 bg-gray-50 rounded text-sm text-gray-700"
              >
                {{ question }}
              </div>
            </div>
            <div v-if="!openingStatementEnabled && openingQuestionsCount === 0" class="text-gray-400 text-sm">
              未配置对话开场白
            </div>
          </div>
        </a-collapse-item>

        <!-- 回答后生成建议问题 -->
        <a-collapse-item key="suggested_after_answer" header="回答后生成建议问题" class="app-ability-item">
          <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-700">状态</span>
            <a-tag :color="suggestedAfterAnswerEnabled ? 'green' : 'gray'" size="small">
              {{ suggestedAfterAnswerEnabled ? '已启用' : '未启用' }}
            </a-tag>
          </div>
        </a-collapse-item>

        <!-- 语音输入 -->
        <a-collapse-item key="speech_to_text" header="语音输入" class="app-ability-item">
          <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-700">状态</span>
            <a-tag :color="speechToTextEnabled ? 'green' : 'gray'" size="small">
              {{ speechToTextEnabled ? '已启用' : '未启用' }}
            </a-tag>
          </div>
        </a-collapse-item>

        <!-- 语音输出 -->
        <a-collapse-item key="text_to_speech" header="语音输出" class="app-ability-item">
          <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-700">状态</span>
            <a-tag :color="textToSpeechEnabled ? 'green' : 'gray'" size="small">
              {{ textToSpeechEnabled ? '已启用' : '未启用' }}
            </a-tag>
          </div>
        </a-collapse-item>

        <!-- 内容审核 -->
        <a-collapse-item key="review_config" header="内容审核" class="app-ability-item">
          <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-700">状态</span>
            <a-tag :color="reviewConfigEnabled ? 'green' : 'gray'" size="small">
              {{ reviewConfigEnabled ? '已启用' : '未启用' }}
            </a-tag>
          </div>
        </a-collapse-item>
      </a-collapse>
    </div>
  </div>
</template>

<style>
.app-ability-readonly .app-ability-item {
  .arco-collapse-item-header {
    background-color: transparent;
    border: none;
  }

  .arco-collapse-item-content {
    padding-left: 16px;
  }
}
</style>
