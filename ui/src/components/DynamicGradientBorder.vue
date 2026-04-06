<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

const containerRef = ref<HTMLDivElement | null>(null)
let animationFrameId: number | null = null

const updateGradient = () => {
  if (!containerRef.value) return

  const time = Date.now() * 0.001
  const hue1 = (time * 30) % 360
  const hue2 = (time * 30 + 120) % 360
  const hue3 = (time * 30 + 240) % 360

  const gradient = `conic-gradient(
    from ${hue1}deg,
    hsl(${hue1}, 100%, 50%),
    hsl(${hue2}, 100%, 50%),
    hsl(${hue3}, 100%, 50%),
    hsl(${hue1}, 100%, 50%)
  )`

  containerRef.value.style.background = gradient
}

const animate = () => {
  updateGradient()
  animationFrameId = requestAnimationFrame(animate)
}

onMounted(() => {
  animate()
})

onUnmounted(() => {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId)
  }
})
</script>

<template>
  <div
    ref="containerRef"
    class="p-1 rounded-full"
    style="background: conic-gradient(from 0deg, hsl(0, 100%, 50%), hsl(120, 100%, 50%), hsl(240, 100%, 50%), hsl(0, 100%, 50%))"
  >
    <slot />
  </div>
</template>

<style scoped>
div {
  transition: background 0.05s linear;
}
</style>
