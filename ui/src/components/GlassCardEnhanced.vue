<script setup lang="ts">
interface Props {
  className?: string
  hoverable?: boolean
  selected?: boolean
  variant?: 'default' | 'message' | 'input'
}

withDefaults(defineProps<Props>(), {
  className: '',
  hoverable: true,
  selected: false,
  variant: 'default',
})
</script>

<template>
  <div
    :class="[
      'rounded-2xl backdrop-blur-xl border transition-all duration-300',
      variant === 'message' && 'bg-white/50 border-white/70 shadow-lg shadow-blue-500/10',
      variant === 'input' && 'bg-white/40 border-white/60 shadow-md shadow-blue-500/5',
      variant === 'default' && 'bg-white/40 border-white/60',
      selected ? 'border-blue-400 bg-blue-50/40 shadow-lg shadow-blue-500/20' : '',
      hoverable && !selected && 'hover:bg-white/50 hover:border-white/80 hover:shadow-lg hover:shadow-blue-500/10',
      className,
    ]"
  >
    <slot />
  </div>
</template>

<style scoped>
/* 增强的玻璃拟态效果 */
div {
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  /* 添加细微的边框光晕 */
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

/* 消息变体的特殊样式 */
:deep(.variant-message) {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.55) 0%, rgba(240, 249, 255, 0.45) 100%);
}

/* 输入变体的特殊样式 */
:deep(.variant-input) {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.45) 0%, rgba(240, 249, 255, 0.35) 100%);
}
</style>
