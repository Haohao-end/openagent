<script setup lang="ts">
import { useGetDraftAppConfig } from '@/hooks/use-app'
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AgentAppAbility from './components/AgentAppAbility.vue'
import ModelConfig from './components/ModelConfig.vue'
import PresetPromptTextarea from './components/PresetPromptTextarea.vue'
import PreviewDebugChat from './components/PreviewDebugChat.vue'
import PreviewDebugHeader from './components/PreviewDebugHeader.vue'

// 1.页面基础数据定义
const route = useRoute()
const props = defineProps({
  app: {
    type: Object,
    default: () => {
      return {}
    },
    required: true,
  },
})
const { draftAppConfigForm, loadDraftAppConfig } = useGetDraftAppConfig()

// 2.页面DOM加载完毕时执行函数
onMounted(async () => {
  await loadDraftAppConfig(String(route.params?.app_id))
})
</script>

<template>
  <div class="flex-1 w-full min-h-0 bg-white">
    <div class="flex-1 grid grid-cols-[26fr_14fr] h-full w-full">
      <!-- 左侧应用编排 -->
      <div class="bg-gray-50 flex flex-col h-full">
        <!-- 顶部标题 -->
        <div class="flex items-center h-16 border-b p-4 gap-4">
          <div class="text-lg text-gray-700">应用编排</div>
          <!-- LLM模型配置 -->
          <model-config :dialog_round="draftAppConfigForm.dialog_round"
            v-model:model_config="draftAppConfigForm.model_config" :app_id="String(route.params?.app_id)" />
        </div>
        <!-- 底部编排区域 -->
        <div class="grid grid-cols-[13fr_13fr] overflow-hidden h-[calc(100vh-141px)]">
          <!-- 左侧人设与回复逻辑 -->
          <div class="border-r py-4">
            <preset-prompt-textarea v-model:preset_prompt="draftAppConfigForm.preset_prompt"
              :app_id="String(route.params?.app_id)" />
          </div>
          <!-- 右侧应用能力 -->
          <agent-app-ability v-model:draft_app_config="draftAppConfigForm" :app_id="String(route.params?.app_id)" />
        </div>
      </div>
      <!-- 右侧调试与会话 -->
      <div class="min-w-[404px] h-full min-h-0 flex flex-col">
        <!-- 头部信息 -->
        <preview-debug-header :app_id="String(route.params?.app_id)"
          :long_term_memory="draftAppConfigForm.long_term_memory" />
        <!-- 对话窗口 -->
        <preview-debug-chat
          class="flex-1 min-h-0"
          :suggested_after_answer="draftAppConfigForm.suggested_after_answer"
          :opening_questions="draftAppConfigForm.opening_questions"
          :opening_statement="draftAppConfigForm.opening_statement" 
          :text_to_speech="draftAppConfigForm.text_to_speech"
          :app="props.app" 
          :app_id="props.app?.id" />
      </div>
    </div>
  </div>
</template>

<style scoped></style>
