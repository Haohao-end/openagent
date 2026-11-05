<script setup lang="ts">
import { useGetDraftAppConfig } from '@/hooks/use-app'
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
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
const { t } = useI18n()
const { draftAppConfigForm, loadDraftAppConfig } = useGetDraftAppConfig()
const isDraftAppConfigRefreshing = ref(false)
let draftAppConfigRefreshQueued = false

const refreshDraftAppConfig = async () => {
  const appId = String(route.params?.app_id ?? '')
  if (!appId) return
  if (isDraftAppConfigRefreshing.value) {
    draftAppConfigRefreshQueued = true
    return
  }

  try {
    isDraftAppConfigRefreshing.value = true
    await loadDraftAppConfig(appId)
  } finally {
    isDraftAppConfigRefreshing.value = false
    if (draftAppConfigRefreshQueued) {
      draftAppConfigRefreshQueued = false
      await refreshDraftAppConfig()
    }
  }
}

// 2.页面DOM加载完毕时执行函数
onMounted(async () => {
  await refreshDraftAppConfig()
})

watch(
  () => [draftAppConfigForm.value.model_config?.provider, draftAppConfigForm.value.model_config?.model],
  async (newValue, oldValue) => {
    if (newValue[0] === oldValue?.[0] && newValue[1] === oldValue?.[1]) return
    await refreshDraftAppConfig()
  },
)
</script>

<template>
  <div class="flex flex-1 min-h-0 w-full flex-col bg-white">
    <div class="grid flex-1 min-h-0 grid-cols-[minmax(0,26fr)_minmax(0,14fr)] w-full overflow-hidden">
      <!-- 左侧应用编排 -->
      <div class="bg-gray-50 flex min-h-0 flex-col min-w-0 overflow-hidden">
        <!-- 顶部标题 -->
        <div class="flex items-center h-16 border-b p-4 gap-4">
          <div class="text-lg text-gray-700">{{ t('appStudio.detail.title') }}</div>
          <!-- LLM模型配置 -->
          <model-config :dialog_round="draftAppConfigForm.dialog_round"
            v-model:model_config="draftAppConfigForm.model_config" :app_id="String(route.params?.app_id)" />
        </div>
        <!-- 底部编排区域 -->
        <div class="grid flex-1 min-h-0 grid-cols-[minmax(0,13fr)_minmax(0,12fr)] overflow-hidden">
          <!-- 左侧人设与回复逻辑 -->
          <div class="border-r py-4 min-w-0 overflow-hidden">
            <preset-prompt-textarea
              class="min-w-0"
              v-model:preset_prompt="draftAppConfigForm.preset_prompt"
              :app_id="String(route.params?.app_id)" />
          </div>
          <!-- 右侧应用能力 -->
          <agent-app-ability
            v-model:draft_app_config="draftAppConfigForm"
            :app_id="String(route.params?.app_id)"
            @reload-draft-app-config="refreshDraftAppConfig"
          />
        </div>
      </div>
      <!-- 右侧调试与会话 -->
      <div class="min-w-[404px] flex min-h-0 flex-col overflow-hidden">
        <!-- 头部信息 -->
        <preview-debug-header :app_id="String(route.params?.app_id)"
          :long_term_memory="draftAppConfigForm.long_term_memory" />
        <!-- 对话窗口 -->
        <preview-debug-chat
          class="flex-1 min-h-0"
          :suggested_after_answer="draftAppConfigForm.suggested_after_answer"
          :opening_questions="draftAppConfigForm.opening_questions"
          :opening_statement="draftAppConfigForm.opening_statement" 
          :capabilities="draftAppConfigForm.capabilities"
          :text_to_speech="draftAppConfigForm.text_to_speech"
          :app="props.app" 
          :app_id="props.app?.id" />
      </div>
    </div>
  </div>
</template>

<style scoped></style>
