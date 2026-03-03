<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AgentAppAbilityReadonly from '@/views/space/apps/components/AgentAppAbilityReadonly.vue'
import ModelConfigReadonly from '@/views/space/apps/components/ModelConfigReadonly.vue'
import PresetPromptTextareaReadonly from '@/views/space/apps/components/PresetPromptTextareaReadonly.vue'
import PreviewDebugChat from '@/views/space/apps/components/PreviewDebugChat.vue'
import PreviewDebugHeader from '@/views/space/apps/components/PreviewDebugHeader.vue'

type DraftAppConfigForm = {
  dialog_round?: number
  model_config?: Record<string, unknown>
  preset_prompt?: string
  long_term_memory?: { enable: boolean }
  suggested_after_answer?: { enable: boolean }
  opening_questions?: string[]
  opening_statement?: string
  text_to_speech?: {
    enable: boolean
    auto_play: boolean
    voice: string
  }
}

type AppPreview = {
  id?: string
  draft_app_config?: DraftAppConfigForm
}

// 1.页面基础数据定义
const route = useRoute()
const props = defineProps({
  app: {
    type: Object as () => AppPreview,
    default: () => {
      return {}
    },
    required: true,
  },
})

const draftAppConfigForm = ref<DraftAppConfigForm>({})

// 2.监听 app 变化，更新配置数据
watch(() => props.app, (newApp) => {
  if (newApp && newApp.draft_app_config) {
    draftAppConfigForm.value = newApp.draft_app_config
  }
}, { immediate: true, deep: true })
</script>

<template>
  <div class="flex-1 w-full min-h-0 bg-white">
    <div class="flex-1 grid grid-cols-[26fr_14fr] h-full w-full">
      <!-- 左侧应用编排 -->
      <div class="bg-gray-50 flex flex-col h-full">
        <!-- 顶部标题 -->
        <div class="flex items-center h-16 border-b p-4 gap-4">
          <div class="text-lg text-gray-700">应用编排（预览）</div>
          <!-- LLM模型配置 -->
          <model-config-readonly
            :dialog_round="draftAppConfigForm.dialog_round"
            :model_config="draftAppConfigForm.model_config" />
        </div>
        <!-- 底部编排区域 -->
        <div class="grid grid-cols-[13fr_13fr] overflow-hidden h-[calc(100vh-141px)]">
          <!-- 左侧人设与回复逻辑 -->
          <div class="border-r py-4">
            <preset-prompt-textarea-readonly
              :preset_prompt="draftAppConfigForm.preset_prompt" />
          </div>
          <!-- 右侧应用能力 -->
          <agent-app-ability-readonly
            :draft_app_config="draftAppConfigForm" />
        </div>
      </div>
      <!-- 右侧调试与会话 -->
      <div class="min-w-[404px] h-full min-h-0 flex flex-col">
        <!-- 头部信息 -->
        <preview-debug-header
          :app_id="String(route.params?.app_id)"
          :long_term_memory="draftAppConfigForm.long_term_memory" />
        <!-- 对话窗口 -->
        <preview-debug-chat
          class="flex-1 min-h-0"
          :suggested_after_answer="draftAppConfigForm.suggested_after_answer"
          :opening_questions="draftAppConfigForm.opening_questions"
          :opening_statement="draftAppConfigForm.opening_statement"
          :text_to_speech="draftAppConfigForm.text_to_speech"
          :app="props.app"
          :app_id="props.app.id" />
      </div>
    </div>
  </div>
</template>

<style scoped></style>
