<script setup lang="ts">
interface Props {
  className?: string
  hoverable?: boolean
  selected?: boolean
}

withDefaults(defineProps<Props>(), {
  className: '',
  hoverable: true,
  selected: false,
})
</script>

<template>
  <div
    :class="[
      'rounded-2xl bg-white/40 backdrop-blur-md border transition-all duration-300',
      selected ? 'border-blue-500 bg-blue-50/40 shadow-lg shadow-blue-500/20' : 'border-white/60',
      hoverable && !selected && 'hover:bg-white/50 hover:border-white/80 hover:shadow-lg hover:shadow-blue-500/10',
      className,
    ]"
  >
    <slot />
  </div>
</template>

<style scoped>
/* Glassmorphism effect */
div {
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
}
</style>
