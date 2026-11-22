<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

let canvas: HTMLCanvasElement
let ctx: CanvasRenderingContext2D
let particles: any[] = []
let animationFrameId: number | null = null
const PARTICLE_COUNT = 80

onMounted(() => {
  canvas = document.getElementById('particle-canvas') as HTMLCanvasElement
  ctx = canvas.getContext('2d')!
  resizeCanvas()
  initParticles()
  animate()
  window.addEventListener('resize', resizeCanvas)
  window.addEventListener('mousemove', handleMouseMove)
})

onUnmounted(() => {
  if (animationFrameId !== null) cancelAnimationFrame(animationFrameId)
  animationFrameId = null
  window.removeEventListener('resize', resizeCanvas)
  window.removeEventListener('mousemove', handleMouseMove)
})

function resizeCanvas() {
  canvas.width = canvas.clientWidth
  canvas.height = canvas.clientHeight
}

function initParticles() {
  particles = Array.from({ length: PARTICLE_COUNT }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    vx: Math.random() * 0.6 - 0.3,
    vy: Math.random() * 0.6 - 0.3,
  }))
}

let mouse: { x: number | null; y: number | null } = { x: null, y: null }
function handleMouseMove(e: MouseEvent) {
  const rect = canvas.getBoundingClientRect()
  mouse.x = e.clientX - rect.left
  mouse.y = e.clientY - rect.top
}

function animate() {
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  particles.forEach((p) => {
    p.x += p.vx
    p.y += p.vy

    if (p.x <= 0 || p.x >= canvas.width) p.vx *= -1
    if (p.y <= 0 || p.y >= canvas.height) p.vy *= -1

    ctx.beginPath()
    ctx.arc(p.x, p.y, 2, 0, Math.PI * 2)
    ctx.fillStyle = '#3b82f6'
    ctx.fill()
  })

  for (let i = 0; i < PARTICLE_COUNT; i++) {
    for (let j = i + 1; j < PARTICLE_COUNT; j++) {
      const dx = particles[i].x - particles[j].x
      const dy = particles[i].y - particles[j].y
      const dist = Math.sqrt(dx * dx + dy * dy)

      if (dist < 100) {
        ctx.strokeStyle = `rgba(59, 130, 246, ${1 - dist / 100})`
        ctx.beginPath()
        ctx.moveTo(particles[i].x, particles[i].y)
        ctx.lineTo(particles[j].x, particles[j].y)
        ctx.stroke()
      }
    }
  }

  // 鼠标连接
  if (mouse.x != null && mouse.y != null) {
  const mx = mouse.x
  const my = mouse.y

  particles.forEach((p) => {
    const dx = p.x - mx
    const dy = p.y - my
    const dist = Math.sqrt(dx * dx + dy * dy)

    if (dist < 100) {
      ctx.strokeStyle = `rgba(14, 165, 233, ${1 - dist / 100})`
      ctx.beginPath()
      ctx.moveTo(p.x, p.y)
      ctx.lineTo(mx, my)
      ctx.stroke()
    }
  })
}



  animationFrameId = requestAnimationFrame(animate)
}
</script>

<template>
  <div class="w-[700px] h-full relative overflow-hidden bg-[#fafeff] text-white flex items-center justify-center">
    <!-- 交互粒子背景 -->
    <canvas id="particle-canvas" class="absolute inset-0 w-full h-full z-0" />

    <!-- 内容 -->
    <div class="relative z-10 text-center px-10">
      <h1 class="text-4xl font-extrabold tracking-wider animate-glow">
        AI Agent 应用开发平台
      </h1>
      <p class="mt-4 text-lg font-extrabold animate-glow leading-relaxed ">
        用AI Agent驱动自动化革命
      </p>
    </div>
  </div>
</template>

<style scoped>
@keyframes glow {
  0%, 100% {
    text-shadow: 0 0 10px #3b82f6, 0 0 20px #0ea5e9, 0 0 30px #0ea5e9;
  }
  50% {
    text-shadow: 0 0 20px #0ea5e9, 0 0 30px #3b82f6, 0 0 50px #1e3a8a;
  }
}

@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-glow {
  animation: glow 3s infinite ease-in-out;
}
.animate-fade-in {
  animation: fade-in 1.5s ease-out;
}
canvas {
  display: block;
}
</style>
