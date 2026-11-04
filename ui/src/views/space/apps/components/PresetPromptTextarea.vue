<script setup lang="ts">
import { useUpdateDraftAppConfig } from '@/hooks/use-app'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import PromptOptimizeTrigger from '@/components/PromptOptimizeTrigger.vue'
import { useI18n } from 'vue-i18n'

// 1.定义自定义组件所需数据
const { t } = useI18n()
const props = defineProps({
  app_id: { type: String, required: true },
  preset_prompt: { type: String, default: '', required: true },
})
const emits = defineEmits(['update:preset_prompt'])
const { handleUpdateDraftAppConfig } = useUpdateDraftAppConfig()

// 2.定义替换预设prompt处理器
const handleReplacePresetPrompt = async (optimizedPrompt: string) => {
  emits('update:preset_prompt', optimizedPrompt)

  try {
    await handleUpdateDraftAppConfig(props.app_id, { preset_prompt: optimizedPrompt })
  } catch (error) {
    console.error('替换预设prompt失败:', error instanceof Error ? error.name : 'unknown_error')
  }
}

// 3.处理编辑器更新
const handleEditorUpdate = (value: string) => {
  emits('update:preset_prompt', value)
}

// 4.处理编辑器失焦
const handleEditorBlur = async () => {
  try {
    await handleUpdateDraftAppConfig(props.app_id, {
      preset_prompt: props.preset_prompt,
    })
  } catch (error) {
    // 错误已在 handleUpdateDraftAppConfig 中处理，这里只是防止未捕获的异常
    console.error('编辑器失焦时更新失败:', error instanceof Error ? error.name : 'unknown_error')
  }
}
</script>

<template>
  <div class="flex flex-col h-full min-w-0">
    <!-- 提示标题 -->
    <div class="flex items-center justify-between px-4 mb-4">
      <div class="text-gray-700 font-bold">{{ t('appStudio.presetPrompt.title') }}</div>
      <a-space :size="8">
        <router-link
          :to="{ name: 'space-apps-prompt-compare', params: { app_id: props.app_id } }"
        >
          <a-button size="mini" class="rounded-lg px-2">
            <template #icon>
              <icon-experiment />
            </template>
            {{ t('appStudio.presetPrompt.compareDebug') }}
          </a-button>
        </router-link>
        <prompt-optimize-trigger @apply="handleReplacePresetPrompt" />
      </a-space>
    </div>
    <!-- Markdown 编辑器容器 -->
    <div class="flex-1 px-4 min-h-0 min-w-0">
      <markdown-editor
        :model-value="props.preset_prompt"
        :placeholder="t('appStudio.presetPrompt.placeholder')"
        :max-length="5000"
        toolbar-variant="compact"
        default-mode="split"
        @update:model-value="handleEditorUpdate"
        @blur="handleEditorBlur"
      />
    </div>
  </div>
</template>
