<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AgentAppAbilityReadonly from '@/views/space/apps/components/AgentAppAbilityReadonly.vue'
import ModelConfigReadonly from '@/views/space/apps/components/ModelConfigReadonly.vue'
import PresetPromptTextareaReadonly from '@/views/space/apps/components/PresetPromptTextareaReadonly.vue'
import PublicPreviewDebugChat from './components/PublicPreviewDebugChat.vue'

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

const route = useRoute()
const props = defineProps({
  app: {
    type: Object as () => AppPreview,
    default: () => ({}),
    required: true,
  },
})

const draftAppConfigForm = ref<DraftAppConfigForm>({})

watch(
  () => props.app,
  (newApp) => {
    if (newApp?.draft_app_config) {
      draftAppConfigForm.value = newApp.draft_app_config
    }
  },
  { immediate: true, deep: true },
)
</script>

<template>
  <div class="w-full h-[calc(100vh-77px)] min-h-0 bg-white overflow-hidden">
    <div class="grid grid-cols-[26fr_14fr] h-full w-full min-h-0 overflow-hidden">
      <div class="bg-gray-50 flex flex-col h-full">
        <div class="flex items-center h-16 border-b p-4 gap-4">
          <div class="text-lg text-gray-700">应用编排</div>
          <model-config-readonly
            :dialog_round="draftAppConfigForm.dialog_round"
            :model_config="draftAppConfigForm.model_config"
          />
        </div>
        <div class="grid grid-cols-[13fr_13fr] overflow-hidden h-[calc(100vh-141px)]">
          <div class="border-r py-4">
            <preset-prompt-textarea-readonly :preset_prompt="draftAppConfigForm.preset_prompt" />
          </div>
          <agent-app-ability-readonly :draft_app_config="draftAppConfigForm" />
        </div>
      </div>
      <div class="min-w-[404px] h-full min-h-0 flex flex-col overflow-hidden">
        <div class="flex items-center justify-between border-b h-[64px] px-4">
          <div class="text-lg text-gray-700">预览与调试</div>
          <a-button size="mini" type="text" class="rounded-lg px-1 !text-blue-700" disabled>
            <template #icon>
              <icon-save />
            </template>
            长期记忆
          </a-button>
        </div>
        <public-preview-debug-chat
          class="flex-1 min-h-0 overflow-hidden"
          :suggested_after_answer="draftAppConfigForm.suggested_after_answer"
          :opening_questions="draftAppConfigForm.opening_questions"
          :opening_statement="draftAppConfigForm.opening_statement"
          :text_to_speech="draftAppConfigForm.text_to_speech"
          :app="props.app"
          :app_id="String(route.params?.app_id)"
        />
      </div>
    </div>
  </div>
</template>
