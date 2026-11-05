<script setup lang="ts">
import { type PropType } from 'vue'
import { useUpdateDraftAppConfig } from '@/hooks/use-app'
import { useI18n } from 'vue-i18n'

// 1.定义自定义组件所需数据
const { t } = useI18n()
const props = defineProps({
  app_id: { type: String, default: '', required: true },
  suggested_after_answer: {
    type: Object as PropType<{ enable: boolean }>,
    default: () => {
      return { enable: false }
    },
    required: true,
  },
})
const emits = defineEmits(['update:suggested_after_answer'])
const { handleUpdateDraftAppConfig } = useUpdateDraftAppConfig()
</script>

<template>
  <div class="">
    <a-collapse-item key="suggested_after_answer" class="app-ability-item">
      <template #header>
        <div class="text-gray-700 font-bold">{{ t('appStudio.abilities.suggestedAfterAnswer.title') }}</div>
      </template>
      <template #extra>
        <a-dropdown
          @select="
            async (value: string | number | boolean) => {
              if (Boolean(value) !== props.suggested_after_answer?.enable) {
                try {
                  await handleUpdateDraftAppConfig(props.app_id, {
                    suggested_after_answer: { enable: Boolean(value) },
                  })
                } catch {
                  return
                }
                emits('update:suggested_after_answer', { enable: Boolean(value) })
              }
            }
          "
        >
          <a-button size="mini" class="rounded-lg flex items-center gap-1 px-1" @click.stop>
            {{
              props.suggested_after_answer.enable
                ? t('appStudio.abilities.suggestedAfterAnswer.on')
                : t('appStudio.abilities.suggestedAfterAnswer.off')
            }}
            <icon-down />
          </a-button>
          <template #content>
            <a-doption :value="1" class="text-xs py-1.5 text-gray-700">
              {{ t('appStudio.abilities.suggestedAfterAnswer.on') }}
            </a-doption>
            <a-doption :value="0" class="text-xs py-1.5 text-red-700">
              {{ t('appStudio.abilities.suggestedAfterAnswer.off') }}
            </a-doption>
          </template>
        </a-dropdown>
      </template>
      <div class="text-xs text-gray-500 leading-[22px]">
        {{ t('appStudio.abilities.suggestedAfterAnswer.description') }}
      </div>
    </a-collapse-item>
  </div>
</template>
