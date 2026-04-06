<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'

interface Props {
  text: string
  highlight?: string
}

const props = withDefaults(defineProps<Props>(), {
  highlight: '',
})

const canvasRef = ref<HTMLCanvasElement | null>(null)
let animationFrameId: number | null = null

// Split text into parts: highlighted and non-highlighted
const parts = computed(() => {
  if (!props.highlight || !props.text) {
    return [{ text: props.text, isHighlight: false }]
  }

  const query = props.highlight.toLowerCase()
  const regex = new RegExp(`(${query})`, 'gi')
  const split = props.text.split(regex)

  return split
    .filter(part => part.length > 0)
    .map(part => ({
      text: part,
      isHighlight: part.toLowerCase() === query,
    }))
})

// Draw animated gradient background for highlights
const drawGradientBackground = (canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, time: number) => {
  const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height)

  const offset = (Math.sin(time * 0.003) + 1) * 0.5

  gradient.addColorStop(0, `rgba(59, 130, 246, ${0.2 + offset * 0.1})`)
  gradient.addColorStop(0.5, `rgba(139, 92, 246, ${0.25 + offset * 0.15})`)
  gradient.addColorStop(1, `rgba(59, 130, 246, ${0.2 + offset * 0.1})`)

  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, canvas.width, canvas.height)
}

const animate = () => {
  const canvas = canvasRef.value
  if (!canvas) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const time = Date.now()
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  drawGradientBackground(canvas, ctx, time)

  animationFrameId = requestAnimationFrame(animate)
}

onMounted(() => {
  const canvas = canvasRef.value
  if (!canvas) return

  canvas.width = canvas.offsetWidth
  canvas.height = canvas.offsetHeight

  animate()
})

onUnmounted(() => {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId)
  }
})
</script>

<template>
  <span class="inline">
    <template v-for="(part, index) in parts" :key="index">
      <span v-if="!part.isHighlight" class="text-gray-700">
        {{ part.text }}
      </span>
      <span v-else class="relative inline-block">
        <canvas
          ref="canvasRef"
          class="absolute inset-0 rounded pointer-events-none"
          style="width: 100%; height: 100%"
        />
        <span class="relative z-10 font-semibold text-gray-900 px-1">
          {{ part.text }}
        </span>
      </span>
    </template>
  </span>
</template>

<style scoped>
canvas {
  image-rendering: auto;
  image-rendering: crisp-edges;
}
</style>
