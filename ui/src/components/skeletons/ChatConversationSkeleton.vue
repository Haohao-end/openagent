<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps({
  pairCount: { type: Number, default: 6, required: false },
})

const rowIndexes = computed(() => Array.from({ length: props.pairCount }, (_, index) => index))
const getBarWidth = (index: number) => {
  const widths = ['100%', '90%', '80%', '68%', '56%', '42%']
  return widths[index % widths.length]
}
const getBarOpacity = (index: number) => {
  const opacities = [1, 0.9, 0.78, 0.62, 0.45, 0.25]
  return opacities[index % opacities.length]
}
</script>

<template>
  <div class="chat-skeleton-container flex flex-col gap-4 py-2">
    <div
      v-for="idx in rowIndexes"
      :key="idx"
      class="skeleton-shimmer h-3.5 rounded-full"
      :style="{ width: getBarWidth(idx), opacity: getBarOpacity(idx) }"
    />
    <div class="skeleton-fade-mask h-8 w-full" />
  </div>
</template>

<style scoped>
.skeleton-shimmer {
  position: relative;
  overflow: hidden;
  background: linear-gradient(
    96deg,
    rgba(226, 232, 240, 0.8) 12%,
    rgba(248, 250, 252, 0.96) 38%,
    rgba(226, 232, 240, 0.7) 64%,
    rgba(248, 250, 252, 0.9) 100%
  );
  background-size: 210% 100%;
  animation: skeleton-shimmer 1.8s ease-in-out infinite;
}

.skeleton-fade-mask {
  background: linear-gradient(to bottom, rgba(248, 250, 252, 0.08), rgba(248, 250, 252, 0.96));
}

@keyframes skeleton-shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}
</style>
