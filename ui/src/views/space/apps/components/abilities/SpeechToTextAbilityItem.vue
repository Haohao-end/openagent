<script setup lang="ts">
import { useUpdateDraftAppConfig } from '@/hooks/use-app'
import { type PropType } from 'vue'

// 1.定义自定义组件所需数据
const props = defineProps({
    app_id: { type: String, default: '', required: true },
    speech_to_text: {
        type: Object as PropType<{ enable: boolean }>,
        default: () => {
            return { enable: false }
        },
        required: true,
    },
})
const emits = defineEmits(['update:speech_to_text'])
const { handleUpdateDraftAppConfig } = useUpdateDraftAppConfig()
</script>

<template>
    <div class="">
        <a-collapse-item key="speech_to_text" class="app-ability-item">
            <template #header>
                <div class="text-gray-700 font-bold">语音输入</div>
            </template>
            <template #extra>
                <a-dropdown @select="
                    async (value: string | number | boolean) => {
                        if (Boolean(value) !== props.speech_to_text?.enable) {
                            emits('update:speech_to_text', { enable: Boolean(value) })
                            await handleUpdateDraftAppConfig(props.app_id, {
                                speech_to_text: { enable: Boolean(value) },
                            })
                        }
                    }
                ">
                    <a-button size="mini" class="rounded-lg flex items-center gap-1 px-1" @click.stop>
                        {{ props.speech_to_text.enable ? '开启' : '关闭' }}
                        <icon-down />
                    </a-button>
                    <template #content>
                        <a-doption :value="1" class="text-xs py-1.5 text-gray-700">开启</a-doption>
                        <a-doption :value="0" class="text-xs py-1.5 text-red-700">关闭</a-doption>
                    </template>
                </a-dropdown>
            </template>
            <div class="text-xs text-gray-500 leading-[22px]">
                启用后，您可以使用语音输入。
            </div>
        </a-collapse-item>
    </div>
</template>
