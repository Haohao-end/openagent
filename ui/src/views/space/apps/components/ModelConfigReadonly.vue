<script setup lang="ts">
import { computed } from 'vue'

// 只读版本的模型配置组件
const props = defineProps({
  model_config: {
    type: Object,
    default: () => {
      return {}
    },
    required: true,
  },
  dialog_round: { type: Number, default: 3, required: true },
})

const modelDisplayName = computed(() => {
  if (!props.model_config?.model) return '未配置'
  return props.model_config.model
})
</script>

<template>
  <div class="flex items-center gap-2">
    <a-tag color="blue" size="small">
      <template #icon>
        <icon-robot />
      </template>
      {{ modelDisplayName }}
    </a-tag>
    <a-tag color="arcoblue" size="small">
      对话轮次: {{ props.dialog_round }}
    </a-tag>
  </div>
</template>

<style scoped></style>
