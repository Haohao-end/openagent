<script setup lang="ts">
import { type PropType } from 'vue'
import { useUpdateDraftAppConfig } from '@/hooks/use-app'
import { useI18n } from 'vue-i18n'

// 1.定义自定义组件所需数据
const { t } = useI18n()
const props = defineProps({
  app_id: { type: String, default: '', required: true },
  long_term_memory: {
    type: Object as PropType<{ enable: boolean }>,
    default: () => {
      return { enable: false }
    },
    required: true,
  },
})
const emits = defineEmits(['update:long_term_memory'])
const { handleUpdateDraftAppConfig } = useUpdateDraftAppConfig()
</script>

<template>
  <div class="">
    <a-collapse-item key="long_term_memory" class="app-ability-item">
      <template #header>
        <div class="text-gray-700 font-bold">{{ t('appStudio.abilities.longTermMemory.title') }}</div>
      </template>
      <template #extra>
        <a-dropdown
          @select="
            async (value: string | number | boolean) => {
              if (Boolean(value) !== props.long_term_memory?.enable) {
                try {
                  await handleUpdateDraftAppConfig(props.app_id, {
                    long_term_memory: { enable: Boolean(value) },
                  })
                } catch {
                  return
                }
                emits('update:long_term_memory', { enable: Boolean(value) })
              }
            }
          "
        >
          <a-button size="mini" class="rounded-lg flex items-center gap-1 px-1" @click.stop>
            {{
              props.long_term_memory.enable
                ? t('appStudio.abilities.longTermMemory.on')
                : t('appStudio.abilities.longTermMemory.off')
            }}
            <icon-down />
          </a-button>
          <template #content>
            <a-doption :value="1" class="text-xs py-1.5 text-gray-700">
              {{ t('appStudio.abilities.longTermMemory.on') }}
            </a-doption>
            <a-doption :value="0" class="text-xs py-1.5 text-red-700">
              {{ t('appStudio.abilities.longTermMemory.off') }}
            </a-doption>
          </template>
        </a-dropdown>
      </template>
      <div class="text-xs text-gray-500 leading-[22px]">
        {{ t('appStudio.abilities.longTermMemory.description') }}
      </div>
    </a-collapse-item>
  </div>
</template>
