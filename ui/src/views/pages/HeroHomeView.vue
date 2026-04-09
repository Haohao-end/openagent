<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import HeroSection from '@/components/HeroSection.vue'
import GlassCard from '@/components/GlassCard.vue'
import AiDynamicBackground from '@/components/AiDynamicBackground.vue'

const scrollPosition = ref(0)
const heroRef = ref<HTMLElement | null>(null)

const handleScroll = (e: Event) => {
  const target = e.target as HTMLElement
  scrollPosition.value = target.scrollTop
}

const scrollToContent = () => {
  if (heroRef.value) {
    const heroHeight = heroRef.value.offsetHeight
    window.scrollTo({
      top: heroHeight,
      behavior: 'smooth',
    })
  }
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll)
})
</script>

<template>
  <div class="relative w-full min-h-screen bg-white overflow-x-hidden">
    <!-- Hero 区域 -->
    <div ref="heroRef" class="relative w-full min-h-screen">
      <HeroSection
        title="Hi，朋友"
        subtitle="你的专属 AI 原生应用开发平台"
        description="说出你的创意，我可以快速帮你创建专属应用，一键轻松分享给朋友，也可以一键发布到 OpenAgent 平台、微信等多个渠道。"
        ctaText="开始创建"
        ctaSecondaryText="了解更多"
      />
    </div>

    <!-- 功能特性区域 -->
    <section class="relative w-full py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-b from-white via-blue-50/20 to-white">
      <AiDynamicBackground
        className="z-0 opacity-40"
        intensity="low"
        :showParticles="false"
        :showGrid="false"
      />

      <div class="relative z-10 max-w-6xl mx-auto">
        <!-- 区域标题 -->
        <div class="text-center mb-16">
          <h2 class="text-4xl sm:text-5xl font-bold text-gray-900 mb-4">
            强大的功能特性
          </h2>
          <p class="text-lg text-gray-600 max-w-2xl mx-auto">
            为开发者和企业提供完整的 AI 应用开发、部署和管理解决方案
          </p>
        </div>

        <!-- 功能卡片网格 -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <!-- 卡片 1 -->
          <GlassCard className="p-8 hover:shadow-xl transition-all duration-300 group">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-blue-400 to-cyan-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">快速创建</h3>
            <p class="text-gray-600">
              通过直观的可视化编辑器，快速创建和配置 AI 应用，无需复杂的代码编写。
            </p>
          </GlassCard>

          <!-- 卡片 2 -->
          <GlassCard className="p-8 hover:shadow-xl transition-all duration-300 group">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">智能优化</h3>
            <p class="text-gray-600">
              内置 AI 优化引擎，自动调整应用参数，提升性能和用户体验。
            </p>
          </GlassCard>

          <!-- 卡片 3 -->
          <GlassCard className="p-8 hover:shadow-xl transition-all duration-300 group">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-green-400 to-emerald-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">灵活配置</h3>
            <p class="text-gray-600">
              支持多种 LLM 模型和工具集成，满足不同场景的应用需求。
            </p>
          </GlassCard>

          <!-- 卡片 4 -->
          <GlassCard className="p-8 hover:shadow-xl transition-all duration-300 group">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-orange-400 to-red-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">一键发布</h3>
            <p class="text-gray-600">
              支持一键发布到多个渠道，包括 OpenAgent 平台、微信、网站等。
            </p>
          </GlassCard>

          <!-- 卡片 5 -->
          <GlassCard className="p-8 hover:shadow-xl transition-all duration-300 group">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-indigo-400 to-blue-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">数据分析</h3>
            <p class="text-gray-600">
              实时监控应用性能，获取详细的用户行为和交互数据分析。
            </p>
          </GlassCard>

          <!-- 卡片 6 -->
          <GlassCard className="p-8 hover:shadow-xl transition-all duration-300 group">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-cyan-400 to-teal-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">安全可靠</h3>
            <p class="text-gray-600">
              企业级安全保障，支持数据加密、访问控制和审计日志。
            </p>
          </GlassCard>
        </div>
      </div>
    </section>

    <!-- CTA 区域 -->
    <section class="relative w-full py-20 px-4 sm:px-6 lg:px-8">
      <AiDynamicBackground
        className="z-0 opacity-30"
        intensity="low"
        :showParticles="true"
        :showGrid="false"
      />

      <div class="relative z-10 max-w-4xl mx-auto">
        <GlassCard className="p-12 text-center">
          <h2 class="text-4xl font-bold text-gray-900 mb-4">
            准备好开始了吗？
          </h2>
          <p class="text-lg text-gray-600 mb-8 max-w-2xl mx-auto">
            加入数千名开发者和企业，使用 OpenAgent 平台创建和部署强大的 AI 应用。
          </p>

          <div class="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              class="group relative px-8 py-4 rounded-xl font-semibold text-white overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/30"
              style="
                background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
              "
            >
              <div
                class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                style="
                  background: linear-gradient(135deg, #06b6d4 0%, #0284c7 100%);
                "
              />
              <span class="relative">立即开始</span>
            </button>

            <button
              class="px-8 py-4 rounded-xl font-semibold text-gray-700 bg-white/40 backdrop-blur-md border border-white/60 hover:bg-white/60 hover:border-white/80 transition-all duration-300"
            >
              查看文档
            </button>
          </div>
        </GlassCard>
      </div>
    </section>

    <!-- 页脚 -->
    <footer class="relative w-full py-12 px-4 sm:px-6 lg:px-8 border-t border-white/20 bg-gradient-to-b from-transparent to-blue-50/30">
      <div class="max-w-6xl mx-auto">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          <div>
            <h3 class="font-bold text-gray-900 mb-4">产品</h3>
            <ul class="space-y-2 text-sm text-gray-600">
              <li><a href="#" class="hover:text-gray-900 transition">功能</a></li>
              <li><a href="#" class="hover:text-gray-900 transition">定价</a></li>
              <li><a href="#" class="hover:text-gray-900 transition">安全</a></li>
            </ul>
          </div>

          <div>
            <h3 class="font-bold text-gray-900 mb-4">开发者</h3>
            <ul class="space-y-2 text-sm text-gray-600">
              <li><a href="#" class="hover:text-gray-900 transition">文档</a></li>
              <li><a href="#" class="hover:text-gray-900 transition">API</a></li>
              <li><a href="#" class="hover:text-gray-900 transition">示例</a></li>
            </ul>
          </div>

          <div>
            <h3 class="font-bold text-gray-900 mb-4">公司</h3>
            <ul class="space-y-2 text-sm text-gray-600">
              <li><a href="#" class="hover:text-gray-900 transition">关于</a></li>
              <li><a href="#" class="hover:text-gray-900 transition">博客</a></li>
              <li><a href="#" class="hover:text-gray-900 transition">联系</a></li>
            </ul>
          </div>

          <div>
            <h3 class="font-bold text-gray-900 mb-4">社区</h3>
            <ul class="space-y-2 text-sm text-gray-600">
              <li><a href="#" class="hover:text-gray-900 transition">Discord</a></li>
              <li><a href="#" class="hover:text-gray-900 transition">GitHub</a></li>
              <li><a href="#" class="hover:text-gray-900 transition">Twitter</a></li>
            </ul>
          </div>
        </div>

        <div class="border-t border-white/20 pt-8 flex flex-col sm:flex-row justify-between items-center text-sm text-gray-600">
          <p>&copy; 2026 OpenAgent. 保留所有权利。</p>
          <div class="flex gap-6 mt-4 sm:mt-0">
            <a href="#" class="hover:text-gray-900 transition">隐私政策</a>
            <a href="#" class="hover:text-gray-900 transition">服务条款</a>
            <a href="#" class="hover:text-gray-900 transition">Cookie 设置</a>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* 平滑滚动 */
html {
  scroll-behavior: smooth;
}
</style>
