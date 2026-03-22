<template>
  <div class="relative w-full min-h-screen overflow-hidden bg-gradient-to-br from-[#F8FBFF] via-[#F6FAFF] to-[#F9FAFB]">
    <!-- 多层背景系统 -->

    <!-- 1. Aurora 极光渐变层 - 主氛围 -->
    <div class="absolute inset-0 overflow-hidden">
      <!-- 大型模糊渐变 blob 1 - 冰蓝 -->
      <div
        class="absolute -top-40 -left-40 w-96 h-96 rounded-full opacity-30 blur-3xl animate-aurora-drift-1"
        style="background: radial-gradient(circle, #AEEBFF 0%, transparent 70%)"
      />

      <!-- 大型模糊渐变 blob 2 - 浅青 -->
      <div
        class="absolute top-1/3 -right-32 w-80 h-80 rounded-full opacity-25 blur-3xl animate-aurora-drift-2"
        style="background: radial-gradient(circle, #8DD8FF 0%, transparent 70%)"
      />

      <!-- 大型模糊渐变 blob 3 - 淡紫 -->
      <div
        class="absolute bottom-1/4 left-1/3 w-96 h-96 rounded-full opacity-20 blur-3xl animate-aurora-drift-3"
        style="background: radial-gradient(circle, #B7B8FF 0%, transparent 70%)"
      />

      <!-- 大型模糊渐变 blob 4 - 浅薄荷 -->
      <div
        class="absolute -bottom-32 right-1/4 w-80 h-80 rounded-full opacity-20 blur-3xl animate-aurora-drift-4"
        style="background: radial-gradient(circle, #C9F7E8 0%, transparent 70%)"
      />
    </div>

    <!-- 2. 微粒子层 -->
    <div class="absolute inset-0 overflow-hidden">
      <div v-for="(particle, idx) in particles" :key="idx" class="absolute animate-particle-float" :style="particle.style">
        <div
          class="w-1 h-1 rounded-full opacity-40"
          :style="{ backgroundColor: particle.color, boxShadow: `0 0 8px ${particle.color}40` }"
        />
      </div>
    </div>

    <!-- 3. 科技网格/光束层 -->
    <div class="absolute inset-0 overflow-hidden opacity-10">
      <svg class="absolute inset-0 w-full h-full" preserveAspectRatio="none">
        <defs>
          <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#7DD3FC" stroke-width="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
      </svg>

      <!-- 轨道光束 -->
      <div class="absolute top-1/4 left-1/4 w-96 h-96 border border-[#A78BFA] rounded-full opacity-20 animate-orbit-slow" />
      <div class="absolute bottom-1/3 right-1/3 w-64 h-64 border border-[#7DD3FC] rounded-full opacity-15 animate-orbit-reverse" />
    </div>

    <!-- 4. 轻噪声纹理层 -->
    <div class="absolute inset-0 opacity-[0.02]" style="background-image: url('data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><filter id=%22noise%22><feTurbulence type=%22fractalNoise%22 baseFrequency=%220.9%22 numOctaves=%224%22 result=%22noise%22/></filter><rect width=%22100%22 height=%22100%22 filter=%22url(%23noise)%22 opacity=%220.5%22/></svg>')" />

    <!-- 前景内容 -->
    <div class="relative z-10 flex flex-col items-center justify-center min-h-screen px-4 sm:px-6 lg:px-8">
      <!-- 顶部装饰标签 -->
      <div class="mb-8 animate-fade-in-down" style="animation-delay: 0.1s">
        <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/40 backdrop-blur-md border border-white/60 shadow-lg shadow-[#7DD3FC]/10">
          <span class="w-2 h-2 rounded-full bg-gradient-to-r from-[#7DD3FC] to-[#A78BFA] animate-pulse" />
          <span class="text-sm font-medium text-[#1F2937]">AI-Powered Platform</span>
        </div>
      </div>

      <!-- 主标题 -->
      <h1 class="max-w-4xl text-5xl sm:text-6xl lg:text-7xl font-bold text-center text-[#111827] leading-tight mb-6 animate-fade-in-down" style="animation-delay: 0.2s">
        Build Intelligent
        <span class="block bg-gradient-to-r from-[#7DD3FC] via-[#A78BFA] to-[#8DD8FF] bg-clip-text text-transparent">
          Workflows Effortlessly
        </span>
      </h1>

      <!-- 副标题 -->
      <p class="max-w-2xl text-lg sm:text-xl text-[#4B5563] text-center mb-12 animate-fade-in-down" style="animation-delay: 0.3s">
        Design, deploy, and scale AI agents with our intuitive platform. No coding required. Pure intelligence.
      </p>

      <!-- CTA 按钮组 -->
      <div class="flex flex-col sm:flex-row gap-4 mb-16 animate-fade-in-down" style="animation-delay: 0.4s">
        <button class="px-8 py-4 rounded-lg font-semibold text-white bg-gradient-to-r from-[#7DD3FC] to-[#A78BFA] hover:shadow-xl hover:shadow-[#7DD3FC]/30 transition-all duration-300 transform hover:scale-105">
          Get Started Free
        </button>
        <button class="px-8 py-4 rounded-lg font-semibold text-[#1F2937] bg-white/50 backdrop-blur-md border border-white/80 hover:bg-white/70 hover:shadow-lg hover:shadow-[#A78BFA]/20 transition-all duration-300">
          Watch Demo
        </button>
      </div>

      <!-- 玻璃拟态展示卡片 -->
      <div class="w-full max-w-3xl animate-fade-in-up" style="animation-delay: 0.5s">
        <div class="relative group">
          <!-- 卡片背景光晕 -->
          <div class="absolute -inset-1 bg-gradient-to-r from-[#7DD3FC]/20 to-[#A78BFA]/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

          <!-- 卡片主体 -->
          <div class="relative bg-white/40 backdrop-blur-xl border border-white/60 rounded-2xl p-8 shadow-2xl shadow-[#7DD3FC]/10">
            <!-- 卡片内部光晕 -->
            <div class="absolute top-0 right-0 w-40 h-40 bg-gradient-to-bl from-[#7DD3FC]/20 to-transparent rounded-full blur-3xl pointer-events-none" />

            <div class="relative z-10">
              <!-- 卡片标题 -->
              <h3 class="text-2xl font-bold text-[#111827] mb-4">Intelligent Workflow Engine</h3>

              <!-- 卡片描述 -->
              <p class="text-[#4B5563] mb-6 leading-relaxed">
                Harness the power of advanced AI models, seamless integrations, and real-time collaboration. Build complex workflows with simple drag-and-drop interface.
              </p>

              <!-- 特性列表 -->
              <div class="grid grid-cols-2 gap-4">
                <div class="flex items-start gap-3">
                  <div class="w-5 h-5 rounded-full bg-gradient-to-br from-[#7DD3FC] to-[#A78BFA] flex items-center justify-center flex-shrink-0 mt-1">
                    <svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                    </svg>
                  </div>
                  <div>
                    <p class="font-semibold text-[#1F2937]">Multi-Model Support</p>
                    <p class="text-sm text-[#6B7280]">GPT, Claude, DeepSeek</p>
                  </div>
                </div>

                <div class="flex items-start gap-3">
                  <div class="w-5 h-5 rounded-full bg-gradient-to-br from-[#7DD3FC] to-[#A78BFA] flex items-center justify-center flex-shrink-0 mt-1">
                    <svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                    </svg>
                  </div>
                  <div>
                    <p class="font-semibold text-[#1F2937]">Real-time Execution</p>
                    <p class="text-sm text-[#6B7280]">Instant feedback & logs</p>
                  </div>
                </div>

                <div class="flex items-start gap-3">
                  <div class="w-5 h-5 rounded-full bg-gradient-to-br from-[#7DD3FC] to-[#A78BFA] flex items-center justify-center flex-shrink-0 mt-1">
                    <svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                    </svg>
                  </div>
                  <div>
                    <p class="font-semibold text-[#1F2937]">Knowledge Base</p>
                    <p class="text-sm text-[#6B7280]">RAG & vector search</p>
                  </div>
                </div>

                <div class="flex items-start gap-3">
                  <div class="w-5 h-5 rounded-full bg-gradient-to-br from-[#7DD3FC] to-[#A78BFA] flex items-center justify-center flex-shrink-0 mt-1">
                    <svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                    </svg>
                  </div>
                  <div>
                    <p class="font-semibold text-[#1F2937]">Team Collaboration</p>
                    <p class="text-sm text-[#6B7280]">Share & iterate together</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部社交证明 -->
      <div class="mt-20 text-center animate-fade-in-up" style="animation-delay: 0.6s">
        <p class="text-sm text-[#6B7280] mb-4">Trusted by leading AI teams</p>
        <div class="flex justify-center gap-8 opacity-60">
          <div class="text-[#9CA3AF] font-semibold">OpenAI</div>
          <div class="text-[#9CA3AF] font-semibold">Anthropic</div>
          <div class="text-[#9CA3AF] font-semibold">DeepSeek</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface Particle {
  style: string
  color: string
}

const particles = ref<Particle[]>([])

onMounted(() => {
  // 生成稀疏的高端感微粒子
  const particleCount = 30
  const colors = ['#7DD3FC', '#A78BFA', '#8DD8FF', '#C9F7E8', '#E6D9FF']

  for (let i = 0; i < particleCount; i++) {
    const x = Math.random() * 100
    const y = Math.random() * 100
    const duration = 15 + Math.random() * 10
    const delay = Math.random() * 5
    const color = colors[Math.floor(Math.random() * colors.length)]

    particles.value.push({
      style: `
        left: ${x}%;
        top: ${y}%;
        animation: particle-float ${duration}s ease-in-out ${delay}s infinite;
      `,
      color
    })
  }
})
</script>

<style scoped>
/* Aurora 极光漂移动画 */
@keyframes aurora-drift-1 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.3;
  }
  25% {
    transform: translate(30px, -40px) scale(1.1);
    opacity: 0.35;
  }
  50% {
    transform: translate(-20px, 30px) scale(0.95);
    opacity: 0.25;
  }
  75% {
    transform: translate(40px, 20px) scale(1.05);
    opacity: 0.3;
  }
}

@keyframes aurora-drift-2 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.25;
  }
  33% {
    transform: translate(-40px, 30px) scale(1.1);
    opacity: 0.3;
  }
  66% {
    transform: translate(30px, -40px) scale(0.9);
    opacity: 0.2;
  }
}

@keyframes aurora-drift-3 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.2;
  }
  40% {
    transform: translate(50px, -30px) scale(1.05);
    opacity: 0.25;
  }
  80% {
    transform: translate(-30px, 40px) scale(0.95);
    opacity: 0.15;
  }
}

@keyframes aurora-drift-4 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.2;
  }
  50% {
    transform: translate(-50px, 40px) scale(1.08);
    opacity: 0.25;
  }
}

/* 微粒子漂浮 */
@keyframes particle-float {
  0%, 100% {
    transform: translateY(0) translateX(0);
    opacity: 0.3;
  }
  25% {
    transform: translateY(-30px) translateX(20px);
    opacity: 0.5;
  }
  50% {
    transform: translateY(-60px) translateX(-20px);
    opacity: 0.3;
  }
  75% {
    transform: translateY(-30px) translateX(30px);
    opacity: 0.4;
  }
}

/* 轨道旋转 */
@keyframes orbit-slow {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes orbit-reverse {
  from {
    transform: rotate(360deg);
  }
  to {
    transform: rotate(0deg);
  }
}

/* 淡入淡出动画 */
@keyframes fade-in-down {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-aurora-drift-1 {
  animation: aurora-drift-1 16s ease-in-out infinite;
}

.animate-aurora-drift-2 {
  animation: aurora-drift-2 18s ease-in-out infinite;
}

.animate-aurora-drift-3 {
  animation: aurora-drift-3 20s ease-in-out infinite;
}

.animate-aurora-drift-4 {
  animation: aurora-drift-4 17s ease-in-out infinite;
}

.animate-particle-float {
  animation: particle-float 20s ease-in-out infinite;
}

.animate-orbit-slow {
  animation: orbit-slow 30s linear infinite;
}

.animate-orbit-reverse {
  animation: orbit-reverse 25s linear infinite;
}

.animate-fade-in-down {
  animation: fade-in-down 0.8s ease-out forwards;
  opacity: 0;
}

.animate-fade-in-up {
  animation: fade-in-up 0.8s ease-out forwards;
  opacity: 0;
}
</style>
