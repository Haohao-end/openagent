<script setup lang="ts">
import { type PropType, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useOptimizePrompt } from '@/hooks/use-ai'

const props = defineProps({
  buttonLabel: { type: String, default: '优化' },
  buttonClass: { type: String, default: 'rounded-lg px-2' },
  buttonSize: {
    type: String as PropType<'mini' | 'small' | 'medium' | 'large'>,
    default: 'mini',
  },
  applyButtonText: { type: String, default: '替换' },
  inputPlaceholder: { type: String, default: '你希望如何编写或优化提示词' },
})
const emits = defineEmits<{
  apply: [prompt: string]
}>()
const popupVisible = ref(false)
const originPrompt = ref('')
const { loading, optimize_prompt, handleOptimizePrompt } = useOptimizePrompt()

const handleSubmit = async () => {
  if (originPrompt.value.trim() === '') {
    Message.warning('原始prompt不能为空')
    return
  }

  await handleOptimizePrompt(originPrompt.value)
}

const handleApply = () => {
  if (optimize_prompt.value.trim() === '') {
    Message.warning('优化prompt为空，请重新生成')
    return
  }

  emits('apply', optimize_prompt.value)
  popupVisible.value = false
}
</script>

<template>
  <a-trigger
    v-model:popup-visible="popupVisible"
    :trigger="['click']"
    position="bl"
    :popup-translate="[0, 8]"
  >
    <a-button :size="props.buttonSize" :class="props.buttonClass">
      <template #icon>
        <icon-sync />
      </template>
      {{ props.buttonLabel }}
    </a-button>
    <template #content>
      <a-card class="rounded-lg w-[422px]">
        <div class="flex flex-col">
          <div v-if="optimize_prompt" class="mb-4 flex flex-col">
            <div class="max-h-[321px] overflow-scroll scrollbar-w-none mb-2 text-gray-700 whitespace-pre-line">
              {{ optimize_prompt }}
            </div>
            <a-space v-if="!loading">
              <a-button
                size="small"
                type="primary"
                class="rounded-lg"
                @click="handleApply"
              >
                {{ props.applyButtonText }}
              </a-button>
              <a-button size="small" class="rounded-lg" @click="popupVisible = false">
                退出
              </a-button>
            </a-space>
          </div>
          <div class="h-[50px] flex items-center gap-2 px-4 flex-1 border border-gray-200 rounded-full">
            <input
              v-model="originPrompt"
              type="text"
              class="flex-1 outline-0"
              :placeholder="props.inputPlaceholder"
            />
            <a-button :loading="loading" type="text" shape="circle" @click="handleSubmit">
              <template #icon>
                <icon-send :size="16" class="!text-blue-700" />
              </template>
            </a-button>
          </div>
        </div>
      </a-card>
    </template>
  </a-trigger>
</template>
