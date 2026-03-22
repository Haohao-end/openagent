<script setup lang="ts">
interface Props {
  className?: string
  intensity?: 'low' | 'medium' | 'high'
}

withDefaults(defineProps<Props>(), {
  className: '',
  intensity: 'medium',
})
</script>

<template>
  <div :class="['absolute inset-0 pointer-events-none overflow-hidden', className]">
    <!-- Animated beam lines -->
    <div
      class="absolute top-0 left-1/4 w-1 h-full bg-gradient-to-b from-blue-400/0 via-blue-400/20 to-blue-400/0 blur-sm"
      :style="{ animation: 'beam-flow 8s ease-in-out infinite' }"
    />
    <div
      class="absolute top-0 right-1/4 w-1 h-full bg-gradient-to-b from-cyan-400/0 via-cyan-400/15 to-cyan-400/0 blur-sm"
      :style="{ animation: 'beam-flow 10s ease-in-out infinite 1s' }"
    />

    <!-- Radial glow -->
    <div
      class="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-gradient-radial from-blue-300/10 to-transparent rounded-full blur-3xl"
      :style="{ animation: 'pulse-glow 6s ease-in-out infinite' }"
    />
  </div>
</template>

<style scoped>
@keyframes beam-flow {
  0%, 100% {
    opacity: 0.1;
    transform: translateY(-100%);
  }
  50% {
    opacity: 0.3;
  }
}

@keyframes pulse-glow {
  0%, 100% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.3;
  }
  50% {
    transform: translate(-50%, -50%) scale(1.2);
    opacity: 0.5;
  }
}
</style>
